from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from .models import CategorySample, IngestPayload, QuantitySample


SCHEMA_PATH = Path("db/schema.sql")


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()


def insert_ingest_batch(conn: sqlite3.Connection, payload: IngestPayload) -> bool:
    """Returns True if batch is new and should be processed."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO ingest_batches(batch_id, device_id, user_id, received_at) VALUES(?,?,?,?)",
        (payload.batch_id, payload.device_id, payload.user_id, int(time.time())),
    )
    return cur.rowcount == 1


def upsert_samples(conn: sqlite3.Connection, payload: IngestPayload) -> tuple[int, int]:
    inserted = 0
    skipped = 0
    now = int(time.time())

    for sample in payload.samples:
        if isinstance(sample, QuantitySample):
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO quantity_samples(
                    id, user_id, type, ts, value, unit, source, device, metadata_json, ingested_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    sample.sample_id,
                    payload.user_id,
                    sample.type,
                    sample.ts,
                    sample.value,
                    sample.unit,
                    sample.source,
                    sample.device,
                    json.dumps(sample.metadata) if sample.metadata is not None else None,
                    now,
                ),
            )
        elif isinstance(sample, CategorySample):
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO category_samples(
                    id, user_id, type, start_ts, end_ts, category, source, device, metadata_json, ingested_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    sample.sample_id,
                    payload.user_id,
                    sample.type,
                    sample.start_ts,
                    sample.end_ts,
                    sample.category,
                    sample.source,
                    sample.device,
                    json.dumps(sample.metadata) if sample.metadata is not None else None,
                    now,
                ),
            )
        else:
            continue

        if cur.rowcount == 1:
            inserted += 1
        else:
            skipped += 1

    conn.commit()
    return inserted, skipped
