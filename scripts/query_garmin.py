#!/usr/bin/env python3
"""Query Garmin data from the local SQLite database.

Usage
-----
    python scripts/query_garmin.py [--window-days 7] [--db db/health.db]

Outputs JSON consumed by the OpenClaw garmin-query skill.
"""
from __future__ import annotations

import argparse
import json
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
    parser = argparse.ArgumentParser(description="Query Garmin data from local SQLite")
    parser.add_argument(
        "--db",
        default=os.environ.get("AHB_DB_PATH", "db/health.db"),
        help="Path to SQLite database",
    )
    parser.add_argument(
        "--user-id",
        default=os.environ.get("AHB_USER_ID", ""),
        help="User identifier (default: AHB_USER_ID)",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=7,
        help="How many days of data to include (default: 7)",
    )
    return parser.parse_args()


def _safe_mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 3) if values else None


def _safe_median(values: list[float]) -> float | None:
    return round(statistics.median(values), 3) if values else None


def _ts_to_iso(ts: int | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _sec_to_min(seconds: int | float | None) -> float | None:
    if seconds is None:
        return None
    return round(seconds / 60, 2)


def main() -> None:
    args = parse_args()
    if not args.user_id:
        raise SystemExit(
            "ERROR: --user-id is required (or set AHB_USER_ID in .env / environment)."
        )

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    now = int(time.time())
    since = now - args.window_days * 86400

    # ── Daily Summaries ───────────────────────────────────────────────────────
    daily_rows = conn.execute(
        """
        SELECT calendar_date, start_ts, steps, distance_meters,
               active_seconds, active_kilocalories, bmr_kilocalories,
               avg_stress_level, max_stress_level,
               avg_heart_rate, resting_heart_rate, min_heart_rate, max_heart_rate,
               body_battery_charged, body_battery_drained,
               moderate_intensity_seconds, vigorous_intensity_seconds,
               floors_climbed, avg_spo2, avg_respiration_rate
        FROM garmin_daily_summaries
        WHERE user_id = ? AND (start_ts >= ? OR start_ts IS NULL)
        ORDER BY calendar_date DESC
        """,
        (args.user_id, since),
    ).fetchall()

    dailies = [dict(row) for row in daily_rows]

    steps_values = [d["steps"] for d in dailies if d["steps"] is not None]
    rhr_values = [d["resting_heart_rate"] for d in dailies if d["resting_heart_rate"] is not None]
    stress_values = [d["avg_stress_level"] for d in dailies if d["avg_stress_level"] is not None]
    bb_charged = [d["body_battery_charged"] for d in dailies if d["body_battery_charged"] is not None]
    bb_drained = [d["body_battery_drained"] for d in dailies if d["body_battery_drained"] is not None]
    active_kcal = [d["active_kilocalories"] for d in dailies if d["active_kilocalories"] is not None]
    spo2_values = [d["avg_spo2"] for d in dailies if d["avg_spo2"] is not None]

    daily_features = {
        "avg_steps": _safe_mean(steps_values),
        "latest_steps": steps_values[0] if steps_values else None,
        "total_steps": sum(steps_values) if steps_values else None,
        "avg_resting_hr": _safe_mean(rhr_values),
        "latest_resting_hr": rhr_values[0] if rhr_values else None,
        "avg_stress_level": _safe_mean(stress_values),
        "latest_stress_level": stress_values[0] if stress_values else None,
        "avg_body_battery_charged": _safe_mean(bb_charged),
        "avg_body_battery_drained": _safe_mean(bb_drained),
        "avg_active_kilocalories": _safe_mean(active_kcal),
        "avg_spo2": _safe_mean(spo2_values),
        "days": len(dailies),
    }

    # ── Sleeps ────────────────────────────────────────────────────────────────
    sleep_rows = conn.execute(
        """
        SELECT summary_id, calendar_date, start_ts, duration_seconds,
               deep_sleep_seconds, light_sleep_seconds, rem_sleep_seconds, awake_seconds,
               avg_spo2, avg_respiration_rate, resting_heart_rate
        FROM garmin_sleeps
        WHERE user_id = ? AND (start_ts >= ? OR start_ts IS NULL)
        ORDER BY calendar_date DESC
        """,
        (args.user_id, since),
    ).fetchall()

    sleeps = []
    for row in sleep_rows:
        d = dict(row)
        d["start_date"] = _ts_to_iso(d["start_ts"])
        d["duration_minutes"] = _sec_to_min(d["duration_seconds"])
        d["deep_sleep_minutes"] = _sec_to_min(d["deep_sleep_seconds"])
        d["light_sleep_minutes"] = _sec_to_min(d["light_sleep_seconds"])
        d["rem_sleep_minutes"] = _sec_to_min(d["rem_sleep_seconds"])
        d["awake_minutes"] = _sec_to_min(d["awake_seconds"])
        total = (d["deep_sleep_seconds"] or 0) + (d["light_sleep_seconds"] or 0) + (d["rem_sleep_seconds"] or 0)
        if total and d["duration_seconds"]:
            d["sleep_efficiency"] = round(total / d["duration_seconds"], 3)
        else:
            d["sleep_efficiency"] = None
        sleeps.append(d)

    sleep_mins = [s["duration_minutes"] for s in sleeps if s["duration_minutes"] is not None]
    deep_mins = [s["deep_sleep_minutes"] for s in sleeps if s["deep_sleep_minutes"] is not None]
    rem_mins = [s["rem_sleep_minutes"] for s in sleeps if s["rem_sleep_minutes"] is not None]
    resp_values = [s["avg_respiration_rate"] for s in sleeps if s["avg_respiration_rate"] is not None]
    eff_values = [s["sleep_efficiency"] for s in sleeps if s["sleep_efficiency"] is not None]

    sleep_features = {
        "avg_duration_minutes": _safe_mean(sleep_mins),
        "latest_duration_minutes": sleep_mins[0] if sleep_mins else None,
        "avg_deep_sleep_minutes": _safe_mean(deep_mins),
        "avg_rem_minutes": _safe_mean(rem_mins),
        "avg_respiration_rate": _safe_mean(resp_values),
        "avg_sleep_efficiency": _safe_mean(eff_values),
        "nights": len(sleeps),
    }

    # ── Activities ────────────────────────────────────────────────────────────
    activity_rows = conn.execute(
        """
        SELECT summary_id, start_ts, activity_type, duration_seconds,
               distance_meters, avg_heart_rate, max_heart_rate,
               active_kilocalories, avg_speed, avg_pace_min_per_km,
               elevation_gain_meters
        FROM garmin_activities
        WHERE user_id = ? AND start_ts >= ?
        ORDER BY start_ts DESC
        """,
        (args.user_id, since),
    ).fetchall()

    activities = []
    for row in activity_rows:
        d = dict(row)
        d["start_date"] = _ts_to_iso(d["start_ts"])
        d["duration_minutes"] = _sec_to_min(d["duration_seconds"])
        activities.append(d)

    act_durations = [a["duration_minutes"] for a in activities if a["duration_minutes"] is not None]
    act_kcal = [a["active_kilocalories"] for a in activities if a["active_kilocalories"] is not None]

    activity_features = {
        "total_activities": len(activities),
        "avg_duration_minutes": _safe_mean(act_durations),
        "total_kilocalories": sum(act_kcal) if act_kcal else None,
        "activity_types": list({a["activity_type"] for a in activities if a["activity_type"]}),
    }

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "user_id": args.user_id,
        "window_days": args.window_days,
        "daily_summaries": dailies,
        "sleeps": sleeps,
        "activities": activities,
        "features": {
            "daily": daily_features,
            "sleep": sleep_features,
            "activity": activity_features,
        },
    }

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
