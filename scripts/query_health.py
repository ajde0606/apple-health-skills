#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from datetime import datetime, timezone


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query Apple Health Bridge SQLite data")
    parser.add_argument("--db", default="db/health.db")
    parser.add_argument("--user-id", default="dad")
    parser.add_argument("--types", default="heart_rate,glucose,sleep_stage")
    parser.add_argument("--window-hours", type=int, default=24)
    parser.add_argument("--sleep-nights", type=int, default=7)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    now = int(time.time())
    since = now - args.window_hours * 3600
    types = [t.strip() for t in args.types.split(",") if t.strip()]

    out: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_hours": args.window_hours,
        "quantity": {},
        "sleep": [],
    }

    for metric in types:
        rows = conn.execute(
            """
            SELECT ts, value, unit, source, device
            FROM quantity_samples
            WHERE user_id = ? AND type = ? AND ts >= ?
            ORDER BY ts DESC
            LIMIT 500
            """,
            (args.user_id, metric, since),
        ).fetchall()
        if rows:
            out["quantity"][metric] = [dict(row) for row in rows]

    sleep_since = now - args.sleep_nights * 86400
    sleep_rows = conn.execute(
        """
        SELECT start_ts, end_ts, category, source, device
        FROM category_samples
        WHERE user_id = ? AND type = 'sleep_stage' AND start_ts >= ?
        ORDER BY start_ts DESC
        LIMIT 1000
        """,
        (args.user_id, sleep_since),
    ).fetchall()
    out["sleep"] = [dict(row) for row in sleep_rows]

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
