#!/usr/bin/env python3
"""Pull data from the Garmin Health API and store it in the local SQLite database.

Usage
-----
    python scripts/sync_garmin.py [--days 7] [--db db/health.db] [--user-id alice]

The script fetches daily summaries, sleep data, and activities for the
requested window and upserts them into the database.  Already-synced records
are skipped (INSERT OR IGNORE).

Run this on a schedule (e.g. cron or launchd) to keep data fresh.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from garmin import client as garmin_client
from garmin import db as garmin_db


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


def _ensure_schema(conn: sqlite3.Connection) -> None:
    schema_path = _repo_root / "db" / "schema.sql"
    conn.executescript(schema_path.read_text())
    conn.commit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Garmin data to local SQLite")
    parser.add_argument(
        "--db",
        default=os.environ.get("AHB_DB_PATH", "db/health.db"),
        help="Path to SQLite database (default: AHB_DB_PATH env or db/health.db)",
    )
    parser.add_argument(
        "--user-id",
        default=os.environ.get("AHB_USER_ID", ""),
        help="User identifier stored alongside each row (default: AHB_USER_ID)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="How many days of history to fetch (default: 7)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.user_id:
        raise SystemExit(
            "ERROR: --user-id is required (or set AHB_USER_ID in .env / environment)."
        )

    now_utc = datetime.now(timezone.utc)
    start_utc = now_utc - timedelta(days=args.days)
    start_ts = int(start_utc.timestamp())
    end_ts = int(now_utc.timestamp())

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)

    print(f"Syncing Garmin data for user={args.user_id} "
          f"from {start_utc.strftime('%Y-%m-%dT%H:%M:%SZ')} to {now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}")

    try:
        print("  Fetching daily summaries…", end=" ", flush=True)
        dailies = garmin_client.fetch_daily_summaries(start_ts, end_ts)
        ins, skp = garmin_db.upsert_daily_summaries(conn, args.user_id, dailies)
        print(f"{len(dailies)} fetched, {ins} inserted, {skp} skipped")

        print("  Fetching sleep data…", end=" ", flush=True)
        sleeps = garmin_client.fetch_sleeps(start_ts, end_ts)
        ins, skp = garmin_db.upsert_sleeps(conn, args.user_id, sleeps)
        print(f"{len(sleeps)} fetched, {ins} inserted, {skp} skipped")

        print("  Fetching activities…", end=" ", flush=True)
        activities = garmin_client.fetch_activities(start_ts, end_ts)
        ins, skp = garmin_db.upsert_activities(conn, args.user_id, activities)
        print(f"{len(activities)} fetched, {ins} inserted, {skp} skipped")

        print("\nSync complete.")
    except Exception as exc:
        raise SystemExit(f"Sync failed: {exc}") from exc
    finally:
        conn.close()


if __name__ == "__main__":
    main()
