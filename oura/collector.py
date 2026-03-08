#!/usr/bin/env python3
"""Oura Ring API collector.

Fetches health data directly from the Oura Cloud API v2 and stores it
in the shared SQLite database using the same schema as the Apple Health
Bridge collector (quantity_samples, category_samples).

Required env vars:
  OURA_PAT       - Oura Personal Access Token
  AHB_USER_ID    - User identifier for data namespacing
  AHB_DB_PATH    - Path to SQLite database (default: db/health.db)

Optional env vars:
  OURA_LOOKBACK_DAYS  - How many days of history to fetch on first run (default: 14)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

OURA_BASE = "https://api.ouraring.com/v2/usercollection"

# Oura sleep-phase integer → category_samples category string
_SLEEP_PHASE_MAP = {
    1: "awake",
    2: "asleepCore",   # light sleep (NREM 1 & 2)
    3: "asleepDeep",   # slow-wave sleep (NREM 3)
    4: "asleepREM",
}


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_repo_root = Path(__file__).resolve().parent.parent
_load_dotenv(_repo_root / ".env")


def _get(path: str, params: dict[str, str], token: str) -> dict[str, Any]:
    """Make a GET request to the Oura API."""
    url = f"{OURA_BASE}/{path}?{urlencode(params)}"
    req = Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except HTTPError as exc:
        raise SystemExit(f"Oura API error {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise SystemExit(f"Network error: {exc.reason}") from exc


def _uid(parts: list[str]) -> str:
    """Deterministic ID from a list of string parts."""
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


def _now_ts() -> int:
    return int(time.time())


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

_SYNC_STATE_DDL = """
CREATE TABLE IF NOT EXISTS oura_sync_state (
    user_id TEXT NOT NULL,
    data_type TEXT NOT NULL,
    last_date TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (user_id, data_type)
);
"""


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_SYNC_STATE_DDL)
    conn.commit()


def _get_last_date(conn: sqlite3.Connection, user_id: str, data_type: str) -> str | None:
    row = conn.execute(
        "SELECT last_date FROM oura_sync_state WHERE user_id = ? AND data_type = ?",
        (user_id, data_type),
    ).fetchone()
    return row[0] if row else None


def _set_last_date(conn: sqlite3.Connection, user_id: str, data_type: str, last_date: str) -> None:
    conn.execute(
        """
        INSERT INTO oura_sync_state (user_id, data_type, last_date, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, data_type) DO UPDATE SET last_date = excluded.last_date, updated_at = excluded.updated_at
        """,
        (user_id, data_type, last_date, _now_ts()),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Heart rate
# ---------------------------------------------------------------------------

def _sync_heartrate(conn: sqlite3.Connection, user_id: str, token: str, start_date: str, end_date: str) -> int:
    """Fetch heart rate samples and upsert into quantity_samples."""
    start_dt = f"{start_date}T00:00:00+00:00"
    end_dt = f"{end_date}T23:59:59+00:00"
    data = _get("heartrate", {"start_datetime": start_dt, "end_datetime": end_dt}, token)
    rows = data.get("data", [])
    ingested = _now_ts()
    inserted = 0
    for item in rows:
        ts_str: str = item.get("timestamp", "")
        bpm = item.get("bpm")
        source = item.get("source", "oura")
        if not ts_str or bpm is None:
            continue
        try:
            ts = int(datetime.fromisoformat(ts_str).timestamp())
        except ValueError:
            continue
        row_id = _uid([user_id, "heart_rate", str(ts), str(bpm)])
        conn.execute(
            """
            INSERT OR IGNORE INTO quantity_samples
              (id, user_id, type, ts, value, unit, source, device, metadata_json, ingested_at)
            VALUES (?, ?, 'heart_rate', ?, ?, 'bpm', ?, 'oura-ring', NULL, ?)
            """,
            (row_id, user_id, ts, float(bpm), source, ingested),
        )
        inserted += conn.execute("SELECT changes()").fetchone()[0]
    conn.commit()
    log.info("heart_rate: fetched %d samples, inserted %d new", len(rows), inserted)
    return inserted


# ---------------------------------------------------------------------------
# HRV (from daily_sleep summary)
# ---------------------------------------------------------------------------

def _sync_hrv(conn: sqlite3.Connection, user_id: str, token: str, start_date: str, end_date: str) -> int:
    """Fetch HRV from daily sleep summaries and upsert into quantity_samples."""
    data = _get("daily_sleep", {"start_date": start_date, "end_date": end_date}, token)
    rows = data.get("data", [])
    ingested = _now_ts()
    inserted = 0
    for item in rows:
        day: str = item.get("day", "")
        hrv = item.get("contributors", {}).get("hrv_balance")
        # average_hrv is in the sleep detail; try top-level first
        avg_hrv = item.get("average_hrv") or hrv
        if not day or avg_hrv is None:
            continue
        try:
            ts = int(datetime.fromisoformat(f"{day}T06:00:00+00:00").timestamp())
        except ValueError:
            continue
        row_id = _uid([user_id, "hrv", day])
        conn.execute(
            """
            INSERT OR IGNORE INTO quantity_samples
              (id, user_id, type, ts, value, unit, source, device, metadata_json, ingested_at)
            VALUES (?, ?, 'hrv', ?, ?, 'ms', 'oura', 'oura-ring', NULL, ?)
            """,
            (row_id, user_id, ts, float(avg_hrv), ingested),
        )
        inserted += conn.execute("SELECT changes()").fetchone()[0]
    conn.commit()
    log.info("hrv: fetched %d days, inserted %d new", len(rows), inserted)
    return inserted


# ---------------------------------------------------------------------------
# Readiness
# ---------------------------------------------------------------------------

def _sync_readiness(conn: sqlite3.Connection, user_id: str, token: str, start_date: str, end_date: str) -> int:
    """Fetch daily readiness scores."""
    data = _get("daily_readiness", {"start_date": start_date, "end_date": end_date}, token)
    rows = data.get("data", [])
    ingested = _now_ts()
    inserted = 0
    for item in rows:
        day: str = item.get("day", "")
        score = item.get("score")
        if not day or score is None:
            continue
        try:
            ts = int(datetime.fromisoformat(f"{day}T06:00:00+00:00").timestamp())
        except ValueError:
            continue
        meta = json.dumps({k: v for k, v in item.get("contributors", {}).items()})
        row_id = _uid([user_id, "readiness_score", day])
        conn.execute(
            """
            INSERT OR IGNORE INTO quantity_samples
              (id, user_id, type, ts, value, unit, source, device, metadata_json, ingested_at)
            VALUES (?, ?, 'readiness_score', ?, ?, 'score', 'oura', 'oura-ring', ?, ?)
            """,
            (row_id, user_id, ts, float(score), meta, ingested),
        )
        inserted += conn.execute("SELECT changes()").fetchone()[0]
    conn.commit()
    log.info("readiness_score: fetched %d days, inserted %d new", len(rows), inserted)
    return inserted


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------

def _sync_activity(conn: sqlite3.Connection, user_id: str, token: str, start_date: str, end_date: str) -> int:
    """Fetch daily activity (steps, calories, active calories)."""
    data = _get("daily_activity", {"start_date": start_date, "end_date": end_date}, token)
    rows = data.get("data", [])
    ingested = _now_ts()
    inserted = 0
    metric_map = [
        ("steps", "step_count", "count"),
        ("total_calories", "energy_burned", "kcal"),
        ("active_calories", "active_energy_burned", "kcal"),
        ("equivalent_walking_distance", "distance", "m"),
    ]
    for item in rows:
        day: str = item.get("day", "")
        if not day:
            continue
        try:
            ts = int(datetime.fromisoformat(f"{day}T12:00:00+00:00").timestamp())
        except ValueError:
            continue
        for api_key, db_type, unit in metric_map:
            val = item.get(api_key)
            if val is None:
                continue
            row_id = _uid([user_id, db_type, day])
            conn.execute(
                """
                INSERT OR IGNORE INTO quantity_samples
                  (id, user_id, type, ts, value, unit, source, device, metadata_json, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?, 'oura', 'oura-ring', NULL, ?)
                """,
                (row_id, user_id, db_type, ts, float(val), unit, ingested),
            )
            inserted += conn.execute("SELECT changes()").fetchone()[0]
    conn.commit()
    log.info("activity: fetched %d days, inserted %d new", len(rows), inserted)
    return inserted


# ---------------------------------------------------------------------------
# Sleep stages
# ---------------------------------------------------------------------------

def _sync_sleep(conn: sqlite3.Connection, user_id: str, token: str, start_date: str, end_date: str) -> int:
    """Fetch sleep sessions and expand phase-5-min string into category_samples."""
    data = _get("sleep", {"start_date": start_date, "end_date": end_date}, token)
    rows = data.get("data", [])
    ingested = _now_ts()
    inserted = 0
    for session in rows:
        bedtime_start: str = session.get("bedtime_start", "")
        phases_str: str = session.get("sleep_phase_5_min", "")
        if not bedtime_start or not phases_str:
            continue
        try:
            session_start = datetime.fromisoformat(bedtime_start)
        except ValueError:
            continue

        interval = 5 * 60  # 5-minute intervals in seconds
        prev_phase: int | None = None
        seg_start: datetime | None = None

        def _flush(phase: int, seg_s: datetime, seg_e: datetime) -> None:
            nonlocal inserted
            category = _SLEEP_PHASE_MAP.get(phase, "awake")
            start_ts = int(seg_s.timestamp())
            end_ts = int(seg_e.timestamp())
            row_id = _uid([user_id, "sleep_stage", str(start_ts), str(end_ts), category])
            conn.execute(
                """
                INSERT OR IGNORE INTO category_samples
                  (id, user_id, type, start_ts, end_ts, category, source, device, metadata_json, ingested_at)
                VALUES (?, ?, 'sleep_stage', ?, ?, ?, 'oura', 'oura-ring', NULL, ?)
                """,
                (row_id, user_id, start_ts, end_ts, category, ingested),
            )
            inserted += conn.execute("SELECT changes()").fetchone()[0]

        for i, ch in enumerate(phases_str):
            try:
                phase = int(ch)
            except ValueError:
                continue
            seg_time = session_start + timedelta(seconds=i * interval)
            if phase != prev_phase:
                if prev_phase is not None and seg_start is not None:
                    _flush(prev_phase, seg_start, seg_time)
                seg_start = seg_time
                prev_phase = phase
        # flush last segment
        if prev_phase is not None and seg_start is not None:
            end_time = session_start + timedelta(seconds=len(phases_str) * interval)
            _flush(prev_phase, seg_start, end_time)

    conn.commit()
    log.info("sleep_stage: fetched %d sessions, inserted %d new category rows", len(rows), inserted)
    return inserted


# ---------------------------------------------------------------------------
# Resting heart rate
# ---------------------------------------------------------------------------

def _sync_resting_hr(conn: sqlite3.Connection, user_id: str, token: str, start_date: str, end_date: str) -> int:
    """Fetch resting heart rate from daily_cardiovascular_age or daily_sleep."""
    # Oura exposes lowest_resting_heart_rate in the sleep endpoint
    data = _get("sleep", {"start_date": start_date, "end_date": end_date}, token)
    rows = data.get("data", [])
    ingested = _now_ts()
    inserted = 0
    for item in rows:
        day: str = (item.get("day") or "")
        rhr = item.get("lowest_resting_heart_rate")
        bedtime_start = item.get("bedtime_start", "")
        if not rhr:
            continue
        try:
            ts = int(datetime.fromisoformat(bedtime_start).timestamp()) if bedtime_start else int(
                datetime.fromisoformat(f"{day}T06:00:00+00:00").timestamp()
            )
        except ValueError:
            continue
        row_id = _uid([user_id, "resting_heart_rate", day])
        conn.execute(
            """
            INSERT OR IGNORE INTO quantity_samples
              (id, user_id, type, ts, value, unit, source, device, metadata_json, ingested_at)
            VALUES (?, ?, 'resting_heart_rate', ?, ?, 'bpm', 'oura', 'oura-ring', NULL, ?)
            """,
            (row_id, user_id, ts, float(rhr), ingested),
        )
        inserted += conn.execute("SELECT changes()").fetchone()[0]
    conn.commit()
    log.info("resting_heart_rate: inserted %d new", inserted)
    return inserted


# ---------------------------------------------------------------------------
# Main sync orchestration
# ---------------------------------------------------------------------------

DATA_TYPES = ["heartrate", "hrv", "readiness", "activity", "sleep", "resting_hr"]

_SYNC_FNS = {
    "heartrate": _sync_heartrate,
    "hrv": _sync_hrv,
    "readiness": _sync_readiness,
    "activity": _sync_activity,
    "sleep": _sync_sleep,
    "resting_hr": _sync_resting_hr,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Oura Ring data into local SQLite")
    parser.add_argument("--db", default=os.environ.get("AHB_DB_PATH", "db/health.db"))
    parser.add_argument("--user-id", default=os.environ.get("AHB_USER_ID", ""))
    parser.add_argument("--token", default=os.environ.get("OURA_PAT", ""))
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=int(os.environ.get("OURA_LOOKBACK_DAYS", "14")),
        help="Days of history to fetch when no prior sync state exists",
    )
    parser.add_argument(
        "--types",
        default=",".join(DATA_TYPES),
        help=f"Comma-separated list of data types to sync: {', '.join(DATA_TYPES)}",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Ignore stored sync state and re-fetch --lookback-days of history",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.token:
        raise SystemExit("ERROR: Oura PAT required — set OURA_PAT in .env or pass --token")
    if not args.user_id:
        raise SystemExit("ERROR: user ID required — set AHB_USER_ID in .env or pass --user-id")

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    _init_db(conn)

    today = date.today()
    end_date = today.isoformat()
    default_start = (today - timedelta(days=args.lookback_days)).isoformat()

    selected = [t.strip() for t in args.types.split(",") if t.strip()]
    total_inserted = 0

    for dtype in selected:
        if dtype not in _SYNC_FNS:
            log.warning("Unknown data type %r — skipping", dtype)
            continue

        if args.full_refresh:
            start_date = default_start
        else:
            last = _get_last_date(conn, args.user_id, dtype)
            start_date = last if last else default_start

        log.info("Syncing %s from %s to %s …", dtype, start_date, end_date)
        try:
            n = _SYNC_FNS[dtype](conn, args.user_id, args.token, start_date, end_date)
            total_inserted += n
            _set_last_date(conn, args.user_id, dtype, end_date)
        except Exception as exc:
            log.error("Failed to sync %s: %s", dtype, exc)

    log.info("Sync complete — %d new rows total", total_inserted)


if __name__ == "__main__":
    main()
