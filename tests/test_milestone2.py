"""
Milestone 2 tests: incremental sync (anchors) + deduplication.

Exit test (plan.md §Milestone 2):
  Sync N days, then add new data, sync again; only new samples appear.

Covers:
  - sample_id determinism (SHA-256 of type|ts|value|source mirrors iOS logic)
  - server idempotency: duplicate sample IDs are silently ignored
  - server idempotency: duplicate batch IDs are treated as no-op success
  - incremental sync: re-sending known samples + new ones inserts only the new ones
  - category (sleep-stage) samples deduplicate correctly
  - mixed quantity + category batches deduplicate correctly
"""

import hashlib

from mac.collector.db import connect, init_db, insert_ingest_batch, upsert_samples
from mac.collector.models import IngestPayload


# ---------------------------------------------------------------------------
# Test-fixture helpers
# ---------------------------------------------------------------------------

def _sample_id(type_: str, ts: int, value: float, source: str) -> str:
    """Compute the deterministic sample ID the same way the iOS app does:
    SHA-256( "type|ts|value|source" ).hexdigest()
    """
    raw = f"{type_}|{ts}|{value}|{source}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _cat_sample_id(type_: str, start_ts: int, end_ts: int, category: str, source: str) -> str:
    """Deterministic ID for category samples (start_ts, end_ts, category all included)."""
    raw = f"{type_}|{start_ts}|{end_ts}|{category}|{source}"
    return hashlib.sha256(raw.encode()).hexdigest()


def qty(type_: str, ts: int, value: float, unit: str, source: str = "Apple Watch") -> dict:
    return {
        "sample_id": _sample_id(type_, ts, value, source),
        "kind": "quantity",
        "type": type_,
        "ts": ts,
        "value": value,
        "unit": unit,
        "source": source,
    }


def cat(type_: str, start_ts: int, end_ts: int, category: str, source: str = "Apple Watch") -> dict:
    return {
        "sample_id": _cat_sample_id(type_, start_ts, end_ts, category, source),
        "kind": "category",
        "type": type_,
        "start_ts": start_ts,
        "end_ts": end_ts,
        "category": category,
        "source": source,
    }


def payload(batch_id: str, samples: list, device: str = "iphone-test01", user: str = "alice") -> IngestPayload:
    return IngestPayload(
        batch_id=batch_id,
        device_id=device,
        user_id=user,
        sent_at=1_700_000_000,
        samples=samples,
    )


def fresh_db(tmp_path):
    conn = connect(str(tmp_path / "health.db"))
    init_db(conn)
    return conn


# ---------------------------------------------------------------------------
# sample_id determinism
# ---------------------------------------------------------------------------

def test_sample_id_same_inputs_produce_same_id():
    """Identical inputs always hash to the same sample_id."""
    id1 = _sample_id("heart_rate", 1_700_000_000, 72.0, "Apple Watch")
    id2 = _sample_id("heart_rate", 1_700_000_000, 72.0, "Apple Watch")
    assert id1 == id2


def test_sample_id_different_type():
    id_hr = _sample_id("heart_rate", 1_700_000_000, 72.0, "Apple Watch")
    id_glu = _sample_id("glucose", 1_700_000_000, 72.0, "Apple Watch")
    assert id_hr != id_glu


def test_sample_id_different_timestamp():
    id1 = _sample_id("heart_rate", 1_700_000_000, 72.0, "Apple Watch")
    id2 = _sample_id("heart_rate", 1_700_000_001, 72.0, "Apple Watch")
    assert id1 != id2


def test_sample_id_different_value():
    id1 = _sample_id("heart_rate", 1_700_000_000, 72.0, "Apple Watch")
    id2 = _sample_id("heart_rate", 1_700_000_000, 73.0, "Apple Watch")
    assert id1 != id2


def test_sample_id_different_source():
    id1 = _sample_id("heart_rate", 1_700_000_000, 72.0, "Apple Watch")
    id2 = _sample_id("heart_rate", 1_700_000_000, 72.0, "iPhone")
    assert id1 != id2


# ---------------------------------------------------------------------------
# Milestone 2 exit test: sync N days, add new data, sync again — only new appears
# ---------------------------------------------------------------------------

def test_incremental_sync_only_new_samples_inserted(tmp_path):
    """
    Exit test for Milestone 2 (plan.md):
      1. Sync an initial N days worth of samples.
      2. Simulate the next incremental sync that re-sends old samples + adds new ones.
      3. Only the new samples should be inserted; old ones are silently skipped.
    """
    conn = fresh_db(tmp_path)

    # Step 1 — initial bootstrap: 3 HR samples from "day 1"
    day1_samples = [
        qty("heart_rate", 1_700_000_000, 62.0, "bpm"),
        qty("heart_rate", 1_700_000_060, 65.0, "bpm"),
        qty("heart_rate", 1_700_000_120, 68.0, "bpm"),
    ]
    p1 = payload("batch-bootstrap", day1_samples)
    assert insert_ingest_batch(conn, p1) is True
    inserted, skipped = upsert_samples(conn, p1)
    assert inserted == 3
    assert skipped == 0

    # Step 2 — incremental sync: same 3 samples + 2 new ones from "day 2"
    day2_new_samples = [
        qty("heart_rate", 1_700_086_400, 70.0, "bpm"),
        qty("heart_rate", 1_700_086_460, 74.0, "bpm"),
    ]
    p2 = payload("batch-incremental", day1_samples + day2_new_samples)
    assert insert_ingest_batch(conn, p2) is True
    inserted, skipped = upsert_samples(conn, p2)
    assert inserted == 2, "Only the 2 new samples should be inserted"
    assert skipped == 3, "The 3 original samples must be skipped (deduplicated)"

    # Verify total count
    row = conn.execute("SELECT COUNT(*) FROM quantity_samples").fetchone()
    assert row[0] == 5


# ---------------------------------------------------------------------------
# Duplicate batch_id → no-op success
# ---------------------------------------------------------------------------

def test_duplicate_batch_id_is_noop(tmp_path):
    """
    Resending the exact same batch (same batch_id) must be a no-op.
    This covers the network-retry / iOS upload-queue retry scenario.
    """
    conn = fresh_db(tmp_path)

    s = qty("glucose", 1_700_000_000, 95.0, "mg_dL")
    p = payload("batch-retry-me", [s])

    # First attempt succeeds
    assert insert_ingest_batch(conn, p) is True
    inserted, _ = upsert_samples(conn, p)
    assert inserted == 1

    # Retry with identical batch_id — must be rejected as duplicate
    assert insert_ingest_batch(conn, p) is False
    inserted, skipped = upsert_samples(conn, p)
    assert inserted == 0
    assert skipped == 1

    # DB still has exactly one row
    row = conn.execute("SELECT COUNT(*) FROM quantity_samples").fetchone()
    assert row[0] == 1


# ---------------------------------------------------------------------------
# Cross-batch sample deduplication
# ---------------------------------------------------------------------------

def test_cross_batch_same_sample_id_inserted_once(tmp_path):
    """
    A sample with the same deterministic ID sent in two *different* batches
    must only be stored once (server-side INSERT OR IGNORE on primary key).
    """
    conn = fresh_db(tmp_path)

    s = qty("heart_rate", 1_700_000_000, 72.0, "bpm")

    p1 = payload("batch-A", [s])
    insert_ingest_batch(conn, p1)
    inserted, skipped = upsert_samples(conn, p1)
    assert (inserted, skipped) == (1, 0)

    p2 = payload("batch-B", [s])
    insert_ingest_batch(conn, p2)
    inserted, skipped = upsert_samples(conn, p2)
    assert (inserted, skipped) == (0, 1)

    row = conn.execute("SELECT COUNT(*) FROM quantity_samples").fetchone()
    assert row[0] == 1


# ---------------------------------------------------------------------------
# Category (sleep-stage) sample deduplication
# ---------------------------------------------------------------------------

def test_category_sample_incremental_sync(tmp_path):
    """Sleep-stage category samples deduplicate correctly across incremental syncs."""
    conn = fresh_db(tmp_path)

    night1 = [
        cat("sleep_stage", 1_700_010_000, 1_700_012_600, "asleepDeep"),
        cat("sleep_stage", 1_700_012_600, 1_700_016_200, "asleepREM"),
    ]
    p1 = payload("sleep-night1", night1)
    insert_ingest_batch(conn, p1)
    inserted, skipped = upsert_samples(conn, p1)
    assert (inserted, skipped) == (2, 0)

    # Night 2: new stage added; previous stages re-sent by anchored query overlap
    night2_new = cat("sleep_stage", 1_700_096_400, 1_700_100_000, "asleepDeep")
    p2 = payload("sleep-night2", night1 + [night2_new])
    insert_ingest_batch(conn, p2)
    inserted, skipped = upsert_samples(conn, p2)
    assert inserted == 1
    assert skipped == 2

    row = conn.execute("SELECT COUNT(*) FROM category_samples").fetchone()
    assert row[0] == 3


# ---------------------------------------------------------------------------
# Mixed quantity + category in same incremental batch
# ---------------------------------------------------------------------------

def test_mixed_types_incremental_sync(tmp_path):
    """Quantity and category samples both deduplicate correctly in the same batch."""
    conn = fresh_db(tmp_path)

    hr = qty("heart_rate", 1_700_000_000, 60.0, "bpm")
    glucose = qty("glucose", 1_700_000_000, 100.0, "mg_dL")
    sleep = cat("sleep_stage", 1_700_010_000, 1_700_012_600, "asleepDeep")

    p1 = payload("mixed-1", [hr, glucose, sleep])
    insert_ingest_batch(conn, p1)
    inserted, skipped = upsert_samples(conn, p1)
    assert (inserted, skipped) == (3, 0)

    # Incremental: re-send all 3, add 1 new HR
    new_hr = qty("heart_rate", 1_700_001_000, 65.0, "bpm")
    p2 = payload("mixed-2", [hr, glucose, sleep, new_hr])
    insert_ingest_batch(conn, p2)
    inserted, skipped = upsert_samples(conn, p2)
    assert inserted == 1
    assert skipped == 3

    qty_count = conn.execute("SELECT COUNT(*) FROM quantity_samples").fetchone()[0]
    cat_count = conn.execute("SELECT COUNT(*) FROM category_samples").fetchone()[0]
    assert qty_count == 3   # hr, glucose, new_hr
    assert cat_count == 1   # sleep
