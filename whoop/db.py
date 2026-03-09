"""SQLite persistence for Whoop data."""
from __future__ import annotations

import sqlite3
import time
from typing import Any


def upsert_cycles(conn: sqlite3.Connection, user_id: str, cycles: list[dict[str, Any]]) -> tuple[int, int]:
    inserted = skipped = 0
    now = int(time.time())
    for cycle in cycles:
        score = cycle.get("score") or {}
        start_ts = _iso_to_ts(cycle.get("start"))
        end_ts = _iso_to_ts(cycle.get("end"))
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO whoop_cycles(
                id, user_id, start_ts, end_ts, strain, kilojoule,
                average_heart_rate, max_heart_rate, synced_at
            ) VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                int(cycle["id"]),
                user_id,
                start_ts,
                end_ts,
                score.get("strain"),
                score.get("kilojoule"),
                score.get("average_heart_rate"),
                score.get("max_heart_rate"),
                now,
            ),
        )
        if cur.rowcount == 1:
            inserted += 1
        else:
            skipped += 1
    conn.commit()
    return inserted, skipped


def upsert_recoveries(conn: sqlite3.Connection, user_id: str, recoveries: list[dict[str, Any]]) -> tuple[int, int]:
    inserted = skipped = 0
    now = int(time.time())
    for rec in recoveries:
        score = rec.get("score") or {}
        ts = _iso_to_ts(rec.get("created_at") or rec.get("updated_at"))
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO whoop_recoveries(
                cycle_id, user_id, ts, recovery_score, resting_heart_rate,
                hrv_rmssd_milli, spo2_percentage, skin_temp_celsius, synced_at
            ) VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                int(rec["cycle_id"]),
                user_id,
                ts,
                score.get("recovery_score"),
                score.get("resting_heart_rate"),
                score.get("hrv_rmssd_milli"),
                score.get("spo2_percentage"),
                score.get("skin_temp_celsius"),
                now,
            ),
        )
        if cur.rowcount == 1:
            inserted += 1
        else:
            skipped += 1
    conn.commit()
    return inserted, skipped


def upsert_sleeps(conn: sqlite3.Connection, user_id: str, sleeps: list[dict[str, Any]]) -> tuple[int, int]:
    inserted = skipped = 0
    now = int(time.time())
    for sleep in sleeps:
        score = sleep.get("score") or {}
        stage_summary = score.get("stage_summary") or {}
        start_ts = _iso_to_ts(sleep.get("start"))
        end_ts = _iso_to_ts(sleep.get("end"))
        total_in_bed = _ms_to_minutes(stage_summary.get("total_in_bed_time_milli"))
        total_sleep = _ms_to_minutes(
            (stage_summary.get("total_slow_wave_sleep_time_milli") or 0)
            + (stage_summary.get("total_rem_sleep_time_milli") or 0)
            + (stage_summary.get("total_light_sleep_time_milli") or 0)
        )
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO whoop_sleeps(
                id, user_id, start_ts, end_ts, nap,
                performance_percentage, respiratory_rate,
                total_in_bed_minutes, total_sleep_minutes,
                stage_sws_minutes, stage_rem_minutes, stage_wake_minutes,
                synced_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                int(sleep["id"]),
                user_id,
                start_ts,
                end_ts,
                1 if sleep.get("nap") else 0,
                score.get("sleep_performance_percentage"),
                score.get("respiratory_rate"),
                total_in_bed,
                total_sleep,
                _ms_to_minutes(stage_summary.get("total_slow_wave_sleep_time_milli")),
                _ms_to_minutes(stage_summary.get("total_rem_sleep_time_milli")),
                _ms_to_minutes(stage_summary.get("total_awake_time_milli")),
                now,
            ),
        )
        if cur.rowcount == 1:
            inserted += 1
        else:
            skipped += 1
    conn.commit()
    return inserted, skipped


def upsert_workouts(conn: sqlite3.Connection, user_id: str, workouts: list[dict[str, Any]]) -> tuple[int, int]:
    inserted = skipped = 0
    now = int(time.time())
    for workout in workouts:
        score = workout.get("score") or {}
        zone_duration = score.get("zone_duration") or {}
        start_ts = _iso_to_ts(workout.get("start"))
        end_ts = _iso_to_ts(workout.get("end"))
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO whoop_workouts(
                id, user_id, start_ts, end_ts, sport_name,
                strain, average_heart_rate, max_heart_rate, kilojoule,
                zone_zero_minutes, zone_one_minutes, zone_two_minutes,
                zone_three_minutes, zone_four_minutes, zone_five_minutes,
                synced_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                int(workout["id"]),
                user_id,
                start_ts,
                end_ts,
                workout.get("sport_name"),
                score.get("strain"),
                score.get("average_heart_rate"),
                score.get("max_heart_rate"),
                score.get("kilojoule"),
                _ms_to_minutes(zone_duration.get("zone_zero_milli")),
                _ms_to_minutes(zone_duration.get("zone_one_milli")),
                _ms_to_minutes(zone_duration.get("zone_two_milli")),
                _ms_to_minutes(zone_duration.get("zone_three_milli")),
                _ms_to_minutes(zone_duration.get("zone_four_milli")),
                _ms_to_minutes(zone_duration.get("zone_five_milli")),
                now,
            ),
        )
        if cur.rowcount == 1:
            inserted += 1
        else:
            skipped += 1
    conn.commit()
    return inserted, skipped


# ── Helpers ───────────────────────────────────────────────────────────────────

def _iso_to_ts(value: str | None) -> int | None:
    if not value:
        return None
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except ValueError:
        return None


def _ms_to_minutes(ms: int | float | None) -> float | None:
    if ms is None:
        return None
    return round(ms / 60_000, 2)
