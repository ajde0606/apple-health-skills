#!/usr/bin/env python3
"""Query Oura Ring data from the local SQLite database.

This script reads data that was synced by oura/collector.py and produces
a structured JSON summary suitable for AI-agent consumption.

Usage:
  python scripts/query_oura.py [options]

Required env / args:
  AHB_USER_ID   - User identifier (or --user-id)
  AHB_DB_PATH   - Path to database (or --db, default: db/health.db)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query Oura Ring data from local SQLite")
    parser.add_argument("--db", default=os.environ.get("AHB_DB_PATH", "db/health.db"))
    parser.add_argument("--user-id", default=os.environ.get("AHB_USER_ID", ""))
    parser.add_argument(
        "--types",
        default="heart_rate,resting_heart_rate,hrv,readiness_score,step_count,energy_burned,sleep_stage",
        help="Comma-separated metric types to include",
    )
    parser.add_argument("--window-hours", type=int, default=24, help="Lookback window for quantity metrics")
    parser.add_argument("--sleep-nights", type=int, default=7, help="Number of nights of sleep data")
    parser.add_argument(
        "--include-features",
        action="store_true",
        default=True,
        help="Compute summary feature statistics (default: true)",
    )
    return parser.parse_args()


def _safe_mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 3) if values else None


def _safe_median(values: list[float]) -> float | None:
    return round(statistics.median(values), 3) if values else None


def _safe_stddev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    return round(statistics.pstdev(values), 3)


def _build_sleep_features(sleep_rows: list[sqlite3.Row], now_ts: int) -> dict:
    nights: dict[str, dict] = {}
    for row in sleep_rows:
        start_ts = int(row["start_ts"])
        end_ts = int(row["end_ts"])
        date_key = datetime.fromtimestamp(start_ts, tz=timezone.utc).date().isoformat()
        night = nights.setdefault(
            date_key,
            {
                "night": date_key,
                "time_in_bed_minutes": 0,
                "total_sleep_minutes": 0,
                "stage_minutes": {"deep": 0, "rem": 0, "core": 0, "other": 0},
                "start_ts": start_ts,
                "end_ts": end_ts,
            },
        )
        minutes = max(0, (end_ts - start_ts) / 60)
        night["time_in_bed_minutes"] += minutes
        category = str(row["category"])
        if category.startswith("asleep"):
            night["total_sleep_minutes"] += minutes
            if category == "asleepDeep":
                night["stage_minutes"]["deep"] += minutes
            elif category == "asleepREM":
                night["stage_minutes"]["rem"] += minutes
            elif category in {"asleepCore", "asleepUnspecified"}:
                night["stage_minutes"]["core"] += minutes
            else:
                night["stage_minutes"]["other"] += minutes
        night["start_ts"] = min(int(night["start_ts"]), start_ts)
        night["end_ts"] = max(int(night["end_ts"]), end_ts)

    nightly = sorted(nights.values(), key=lambda n: n["night"], reverse=True)
    for night in nightly:
        tib = float(night["time_in_bed_minutes"])
        asleep = float(night["total_sleep_minutes"])
        night["time_in_bed_minutes"] = round(tib, 2)
        night["total_sleep_minutes"] = round(asleep, 2)
        night["sleep_efficiency"] = round(asleep / tib, 3) if tib > 0 else None
        for stage, val in night["stage_minutes"].items():
            night["stage_minutes"][stage] = round(float(val), 2)

    bedtimes = [int(n["start_ts"]) % 86400 for n in nightly]
    waketimes = [int(n["end_ts"]) % 86400 for n in nightly]
    sleep_consistency = {
        "bedtime_variance_minutes": round(math.sqrt(statistics.pvariance(bedtimes)) / 60, 2)
        if len(bedtimes) > 1 else None,
        "waketime_variance_minutes": round(math.sqrt(statistics.pvariance(waketimes)) / 60, 2)
        if len(waketimes) > 1 else None,
    }

    return {
        "recent_nights": nightly,
        "rolling": {
            "avg_total_sleep_minutes": _safe_mean([float(n["total_sleep_minutes"]) for n in nightly]),
            "avg_time_in_bed_minutes": _safe_mean([float(n["time_in_bed_minutes"]) for n in nightly]),
            "avg_sleep_efficiency": _safe_mean(
                [float(n["sleep_efficiency"]) for n in nightly if n["sleep_efficiency"] is not None]
            ),
            "sleep_consistency": sleep_consistency,
            "window_end_ts": now_ts,
        },
    }


def _build_readiness_features(readiness_rows: list[sqlite3.Row]) -> dict:
    scores = [float(r["value"]) for r in readiness_rows]
    latest = readiness_rows[0] if readiness_rows else None
    latest_contributors: dict = {}
    if latest and latest["metadata_json"]:
        try:
            latest_contributors = json.loads(str(latest["metadata_json"]))
        except (json.JSONDecodeError, TypeError):
            pass
    return {
        "latest_score": scores[0] if scores else None,
        "avg_score": _safe_mean(scores),
        "min_score": round(min(scores), 3) if scores else None,
        "max_score": round(max(scores), 3) if scores else None,
        "latest_contributors": latest_contributors,
        "samples": len(scores),
    }


def _build_heart_features(hr_rows: list[sqlite3.Row], rhr_rows: list[sqlite3.Row], hrv_rows: list[sqlite3.Row]) -> dict:
    hr_values = [float(r["value"]) for r in hr_rows]
    rhr_values = [float(r["value"]) for r in rhr_rows]
    hrv_values = [float(r["value"]) for r in hrv_rows]
    return {
        "median_hr": _safe_median(hr_values),
        "avg_hr": _safe_mean(hr_values),
        "resting_hr_avg": _safe_mean(rhr_values),
        "resting_hr_latest": rhr_values[0] if rhr_values else None,
        "hrv_avg": _safe_mean(hrv_values),
        "hrv_latest": hrv_values[0] if hrv_values else None,
        "hr_samples": len(hr_values),
        "hrv_samples": len(hrv_values),
    }


def _build_activity_features(step_rows: list[sqlite3.Row], cal_rows: list[sqlite3.Row]) -> dict:
    steps = [float(r["value"]) for r in step_rows]
    cals = [float(r["value"]) for r in cal_rows]
    return {
        "avg_daily_steps": _safe_mean(steps),
        "total_steps_window": round(sum(steps), 0) if steps else None,
        "avg_active_calories": _safe_mean(cals),
        "samples_days": len(steps),
    }


def _get_sync_state(conn: sqlite3.Connection, user_id: str) -> dict:
    try:
        rows = conn.execute(
            "SELECT data_type, last_date, updated_at FROM oura_sync_state WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        return {r["data_type"]: {"last_date": r["last_date"], "updated_at": r["updated_at"]} for r in rows}
    except sqlite3.OperationalError:
        return {}


def main() -> None:
    args = parse_args()

    if not args.user_id:
        raise SystemExit("ERROR: --user-id is required (or set AHB_USER_ID in .env).")

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    now = int(time.time())
    since = now - args.window_hours * 3600
    sleep_since = now - args.sleep_nights * 86400
    types = [t.strip() for t in args.types.split(",") if t.strip()]

    out: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "user_id": args.user_id,
        "source": "oura",
        "window_hours": args.window_hours,
        "quantity": {},
        "sleep": [],
        "features": {},
        "sync_state": _get_sync_state(conn, args.user_id),
    }

    # Fetch quantity metrics
    quantity_types = [t for t in types if t != "sleep_stage"]
    for metric in quantity_types:
        rows = conn.execute(
            """
            SELECT ts, value, unit, source, device, metadata_json
            FROM quantity_samples
            WHERE user_id = ? AND type = ? AND ts >= ? AND source IN ('oura', 'oura-ring')
            ORDER BY ts DESC
            LIMIT 500
            """,
            (args.user_id, metric, since),
        ).fetchall()
        if rows:
            out["quantity"][metric] = [dict(r) for r in rows]

    # Fetch sleep stages
    if "sleep_stage" in types:
        sleep_rows = conn.execute(
            """
            SELECT start_ts, end_ts, category, source, device
            FROM category_samples
            WHERE user_id = ? AND type = 'sleep_stage' AND start_ts >= ? AND source = 'oura'
            ORDER BY start_ts DESC
            LIMIT 2000
            """,
            (args.user_id, sleep_since),
        ).fetchall()
        out["sleep"] = [dict(r) for r in sleep_rows]
    else:
        sleep_rows = []

    if args.include_features:
        hr_rows = conn.execute(
            """
            SELECT ts, value, unit, source
            FROM quantity_samples
            WHERE user_id = ? AND type = 'heart_rate' AND ts >= ? AND source IN ('oura', 'oura-ring')
            ORDER BY ts DESC LIMIT 1000
            """,
            (args.user_id, since),
        ).fetchall()
        rhr_rows = conn.execute(
            """
            SELECT ts, value, unit, source
            FROM quantity_samples
            WHERE user_id = ? AND type = 'resting_heart_rate' AND ts >= ? AND source IN ('oura', 'oura-ring')
            ORDER BY ts DESC LIMIT 100
            """,
            (args.user_id, since),
        ).fetchall()
        hrv_rows = conn.execute(
            """
            SELECT ts, value, unit, source
            FROM quantity_samples
            WHERE user_id = ? AND type = 'hrv' AND ts >= ? AND source IN ('oura', 'oura-ring')
            ORDER BY ts DESC LIMIT 100
            """,
            (args.user_id, since),
        ).fetchall()
        readiness_rows = conn.execute(
            """
            SELECT ts, value, unit, source, metadata_json
            FROM quantity_samples
            WHERE user_id = ? AND type = 'readiness_score' AND ts >= ? AND source IN ('oura', 'oura-ring')
            ORDER BY ts DESC LIMIT 30
            """,
            (args.user_id, since),
        ).fetchall()
        step_rows = conn.execute(
            """
            SELECT ts, value, unit
            FROM quantity_samples
            WHERE user_id = ? AND type = 'step_count' AND ts >= ? AND source IN ('oura', 'oura-ring')
            ORDER BY ts DESC LIMIT 30
            """,
            (args.user_id, since),
        ).fetchall()
        cal_rows = conn.execute(
            """
            SELECT ts, value, unit
            FROM quantity_samples
            WHERE user_id = ? AND type = 'active_energy_burned' AND ts >= ? AND source IN ('oura', 'oura-ring')
            ORDER BY ts DESC LIMIT 30
            """,
            (args.user_id, since),
        ).fetchall()

        out["features"] = {
            "sleep": _build_sleep_features(sleep_rows, now),
            "heart": _build_heart_features(hr_rows, rhr_rows, hrv_rows),
            "readiness": _build_readiness_features(readiness_rows),
            "activity": _build_activity_features(step_rows, cal_rows),
        }

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
