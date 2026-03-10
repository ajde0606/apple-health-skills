"""SQLite persistence for Garmin data."""
from __future__ import annotations

import sqlite3
import time
from typing import Any


def upsert_daily_summaries(
    conn: sqlite3.Connection,
    user_id: str,
    summaries: list[dict[str, Any]],
) -> tuple[int, int]:
    inserted = skipped = 0
    now = int(time.time())
    for s in summaries:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO garmin_daily_summaries(
                summary_id, user_id, calendar_date, start_ts,
                steps, distance_meters, active_seconds, active_kilocalories,
                bmr_kilocalories, avg_stress_level, max_stress_level,
                avg_heart_rate, resting_heart_rate, min_heart_rate, max_heart_rate,
                body_battery_charged, body_battery_drained,
                moderate_intensity_seconds, vigorous_intensity_seconds,
                floors_climbed, avg_spo2, avg_respiration_rate,
                synced_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                s.get("summaryId"),
                user_id,
                s.get("calendarDate"),
                s.get("startTimeInSeconds"),
                s.get("steps"),
                s.get("distanceInMeters"),
                s.get("activeTimeInSeconds"),
                s.get("activeKilocalories"),
                s.get("bmrKilocalories"),
                s.get("averageStressLevel"),
                s.get("maxStressLevel"),
                s.get("averageHeartRateInBeatsPerMinute"),
                s.get("restingHeartRateInBeatsPerMinute"),
                s.get("minHeartRateInBeatsPerMinute"),
                s.get("maxHeartRateInBeatsPerMinute"),
                s.get("bodyBatteryChargedValue"),
                s.get("bodyBatteryDrainedValue"),
                s.get("moderateIntensityDurationInSeconds"),
                s.get("vigorousIntensityDurationInSeconds"),
                s.get("floorsClimbed"),
                s.get("averageSpo2"),
                s.get("averageRespirationRate"),
                now,
            ),
        )
        if cur.rowcount == 1:
            inserted += 1
        else:
            skipped += 1
    conn.commit()
    return inserted, skipped


def upsert_sleeps(
    conn: sqlite3.Connection,
    user_id: str,
    sleeps: list[dict[str, Any]],
) -> tuple[int, int]:
    inserted = skipped = 0
    now = int(time.time())
    for s in sleeps:
        validation = s.get("sleepLevelsMap") or {}
        deep_seconds = sum(
            seg.get("endTimeInSeconds", 0) - seg.get("startTimeInSeconds", 0)
            for seg in validation.get("deep", [])
        )
        light_seconds = sum(
            seg.get("endTimeInSeconds", 0) - seg.get("startTimeInSeconds", 0)
            for seg in validation.get("light", [])
        )
        rem_seconds = sum(
            seg.get("endTimeInSeconds", 0) - seg.get("startTimeInSeconds", 0)
            for seg in validation.get("rem", [])
        )
        awake_seconds = sum(
            seg.get("endTimeInSeconds", 0) - seg.get("startTimeInSeconds", 0)
            for seg in validation.get("awake", [])
        )

        # Prefer explicit fields when available (newer API versions)
        deep_sec = s.get("deepSleepDurationInSeconds", deep_seconds) or deep_seconds
        light_sec = s.get("lightSleepDurationInSeconds", light_seconds) or light_seconds
        rem_sec = s.get("remSleepInSeconds", rem_seconds) or rem_seconds
        awake_sec = s.get("awakeDurationInSeconds", awake_seconds) or awake_seconds

        cur = conn.execute(
            """
            INSERT OR IGNORE INTO garmin_sleeps(
                summary_id, user_id, calendar_date, start_ts, duration_seconds,
                deep_sleep_seconds, light_sleep_seconds, rem_sleep_seconds, awake_seconds,
                avg_spo2, avg_respiration_rate, resting_heart_rate,
                synced_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                s.get("summaryId"),
                user_id,
                s.get("calendarDate"),
                s.get("startTimeInSeconds"),
                s.get("durationInSeconds"),
                deep_sec,
                light_sec,
                rem_sec,
                awake_sec,
                s.get("averageSpO2Value"),
                s.get("averageRespirationValue"),
                s.get("restingHeartRate"),
                now,
            ),
        )
        if cur.rowcount == 1:
            inserted += 1
        else:
            skipped += 1
    conn.commit()
    return inserted, skipped


def upsert_activities(
    conn: sqlite3.Connection,
    user_id: str,
    activities: list[dict[str, Any]],
) -> tuple[int, int]:
    inserted = skipped = 0
    now = int(time.time())
    for a in activities:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO garmin_activities(
                summary_id, user_id, start_ts, activity_type,
                duration_seconds, distance_meters,
                avg_heart_rate, max_heart_rate, active_kilocalories,
                avg_speed, avg_pace_min_per_km, elevation_gain_meters,
                synced_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                a.get("summaryId"),
                user_id,
                a.get("startTimeInSeconds"),
                a.get("activityType"),
                a.get("durationInSeconds"),
                a.get("distanceInMeters"),
                a.get("averageHeartRateInBeatsPerMinute"),
                a.get("maxHeartRateInBeatsPerMinute"),
                a.get("activeKilocalories"),
                a.get("averageSpeed"),
                a.get("averagePaceInMinutesPerKilometer"),
                a.get("totalElevationGainInMeters"),
                now,
            ),
        )
        if cur.rowcount == 1:
            inserted += 1
        else:
            skipped += 1
    conn.commit()
    return inserted, skipped
