#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path


def _load_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def _upsert_env_key(path: Path, key: str, value: str) -> None:
    lines = path.read_text().splitlines() if path.exists() else []
    replaced = False
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}="):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        if out and out[-1] != "":
            out.append("")
        out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n")


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def cmd_rotate_token(args: argparse.Namespace) -> None:
    token = secrets.token_urlsafe(32)
    _upsert_env_key(Path(args.env_file), "AHB_INGEST_TOKEN", token)
    print(json.dumps({"ok": True, "token": token, "env_file": args.env_file}, indent=2))


def cmd_last_sync(args: argparse.Namespace) -> None:
    conn = _connect(args.db)
    row = conn.execute(
        """
        SELECT batch_id, device_id, user_id, received_at
        FROM ingest_batches
        ORDER BY received_at DESC
        LIMIT 1
        """
    ).fetchone()
    qty = conn.execute("SELECT COUNT(*) AS n FROM quantity_samples").fetchone()["n"]
    cat = conn.execute("SELECT COUNT(*) AS n FROM category_samples").fetchone()["n"]
    payload = {
        "latest_sync": dict(row) if row else None,
        "latest_sync_iso": datetime.fromtimestamp(row["received_at"], tz=timezone.utc).isoformat() if row else None,
        "quantity_samples": qty,
        "category_samples": cat,
    }
    print(json.dumps(payload, indent=2))


def cmd_export_json(args: argparse.Namespace) -> None:
    since = int(time.time()) - args.days * 86400
    conn = _connect(args.db)
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "days": args.days,
        "quantity_samples": [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM quantity_samples WHERE ts >= ? ORDER BY ts DESC",
                (since,),
            ).fetchall()
        ],
        "category_samples": [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM category_samples WHERE end_ts >= ? ORDER BY end_ts DESC",
                (since,),
            ).fetchall()
        ],
        "ingest_batches": [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM ingest_batches WHERE received_at >= ? ORDER BY received_at DESC",
                (since,),
            ).fetchall()
        ],
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"ok": True, "output": str(out_path), "days": args.days}, indent=2))


def cmd_purge(args: argparse.Namespace) -> None:
    cutoff = int(time.time()) - args.days * 86400
    conn = _connect(args.db)
    qty_deleted = conn.execute("DELETE FROM quantity_samples WHERE ts < ?", (cutoff,)).rowcount
    cat_deleted = conn.execute("DELETE FROM category_samples WHERE end_ts < ?", (cutoff,)).rowcount
    batch_deleted = conn.execute("DELETE FROM ingest_batches WHERE received_at < ?", (cutoff,)).rowcount
    conn.commit()
    print(
        json.dumps(
            {
                "ok": True,
                "retention_days": args.days,
                "deleted": {
                    "quantity_samples": qty_deleted,
                    "category_samples": cat_deleted,
                    "ingest_batches": batch_deleted,
                },
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apple Health Bridge admin CLI")
    parser.add_argument("--env-file", default=".env", help="Path to .env (default: .env)")
    parser.add_argument("--db", default="db/health.db", help="Path to SQLite db (default: db/health.db)")
    sub = parser.add_subparsers(dest="command", required=True)

    rotate = sub.add_parser("rotate-token", help="Generate and store a new ingest token in .env")
    rotate.set_defaults(func=cmd_rotate_token)

    last_sync = sub.add_parser("last-sync", help="Show latest successful ingest metadata")
    last_sync.set_defaults(func=cmd_last_sync)

    export = sub.add_parser("export-json", help="Export recent data to JSON for debugging")
    export.add_argument("--days", type=int, default=7, help="Window size in days (default: 7)")
    export.add_argument("--output", default="exports/health_export_last7d.json")
    export.set_defaults(func=cmd_export_json)

    purge = sub.add_parser("purge", help="Delete data older than retention window")
    purge.add_argument("--days", type=int, required=True, help="Keep this many days of data")
    purge.set_defaults(func=cmd_purge)

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
