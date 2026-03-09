#!/usr/bin/env python3
"""Pull data from the Whoop API and store it in the local SQLite database.

Usage
-----
    python scripts/sync_whoop.py [--days 7] [--db db/health.db] [--user-id alice]

The script fetches cycles, recoveries, sleeps, and workouts for the requested
window and upserts them into the database.  Already-synced records are skipped
(INSERT OR IGNORE).

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

from whoop import client as whoop_client
from whoop import db as whoop_db


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
    _migrate_text_ids(conn)


def _migrate_text_ids(conn: sqlite3.Connection) -> None:
    """Recreate whoop_sleeps/whoop_workouts if their id column is INTEGER.

    The Whoop v2 API returns UUID strings for sleep/workout IDs.  Old DBs
    created before this migration have id INTEGER PRIMARY KEY, which rejects
    UUID strings with 'datatype mismatch'.  Since those tables were always
    empty (all requests 404'd under the old code), dropping them is safe.
    """
    for table in ("whoop_sleeps", "whoop_workouts"):
        rows = conn.execute(
            f"PRAGMA table_info({table})"  # noqa: S608
        ).fetchall()
        if not rows:
            continue  # table doesn't exist yet
        id_col = next((r for r in rows if r[1] == "id"), None)
        if id_col and id_col[2].upper() == "INTEGER":
            conn.execute(f"DROP TABLE {table}")
    conn.commit()
    # Re-run CREATE TABLE IF NOT EXISTS now that old tables are gone.
    schema_path = _repo_root / "db" / "schema.sql"
    conn.executescript(schema_path.read_text())
    conn.commit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Whoop data to local SQLite")
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
    start_iso = start_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)

    print(f"Syncing Whoop data for user={args.user_id} from {start_iso} to {end_iso}")

    try:
        print("  Fetching cycles…", end=" ", flush=True)
        cycles = whoop_client.fetch_cycles(start=start_iso, end=end_iso)
        ins, skp = whoop_db.upsert_cycles(conn, args.user_id, cycles)
        print(f"{len(cycles)} fetched, {ins} inserted, {skp} skipped")

        print("  Fetching recoveries…", end=" ", flush=True)
        recoveries = whoop_client.fetch_recoveries(start=start_iso, end=end_iso)
        ins, skp = whoop_db.upsert_recoveries(conn, args.user_id, recoveries)
        print(f"{len(recoveries)} fetched, {ins} inserted, {skp} skipped")

        print("  Fetching sleeps…", end=" ", flush=True)
        sleeps = whoop_client.fetch_sleeps(start=start_iso, end=end_iso)
        ins, skp = whoop_db.upsert_sleeps(conn, args.user_id, sleeps)
        print(f"{len(sleeps)} fetched, {ins} inserted, {skp} skipped")

        print("  Fetching workouts…", end=" ", flush=True)
        workouts = whoop_client.fetch_workouts(start=start_iso, end=end_iso)
        ins, skp = whoop_db.upsert_workouts(conn, args.user_id, workouts)
        print(f"{len(workouts)} fetched, {ins} inserted, {skp} skipped")

        print("\nSync complete.")
    except Exception as exc:
        raise SystemExit(f"Sync failed: {exc}") from exc
    finally:
        conn.close()


if __name__ == "__main__":
    main()
