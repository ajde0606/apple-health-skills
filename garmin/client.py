"""Garmin Connect API client.

Wraps the Garmin Health API (Wellness API) with OAuth 1.0a authentication.

API reference: https://developer.garmin.com/gc-developer-program/health-api/
"""
from __future__ import annotations

from typing import Any

from .auth import get_oauth_session

BASE_URL = "https://apis.garmin.com/wellness-api/rest"


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    session = get_oauth_session()
    resp = session.get(
        f"{BASE_URL}{path}",
        params=params or {},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ── High-level fetch helpers ─────────────────────────────────────────────────

def fetch_daily_summaries(
    upload_start_ts: int,
    upload_end_ts: int,
) -> list[dict[str, Any]]:
    """Fetch daily activity summaries.

    Parameters are Unix timestamps (seconds) for the upload time window.
    Returns a list of daily summary records.
    """
    data = _get(
        "/dailies",
        params={
            "uploadStartTimeInSeconds": upload_start_ts,
            "uploadEndTimeInSeconds": upload_end_ts,
        },
    )
    return data.get("dailies", [])


def fetch_sleeps(
    upload_start_ts: int,
    upload_end_ts: int,
) -> list[dict[str, Any]]:
    """Fetch sleep summary records."""
    data = _get(
        "/sleepData",
        params={
            "uploadStartTimeInSeconds": upload_start_ts,
            "uploadEndTimeInSeconds": upload_end_ts,
        },
    )
    return data.get("sleeps", [])


def fetch_activities(
    upload_start_ts: int,
    upload_end_ts: int,
) -> list[dict[str, Any]]:
    """Fetch activity (workout) records."""
    data = _get(
        "/activities",
        params={
            "uploadStartTimeInSeconds": upload_start_ts,
            "uploadEndTimeInSeconds": upload_end_ts,
        },
    )
    return data.get("activities", [])


def fetch_heart_rate_data(
    upload_start_ts: int,
    upload_end_ts: int,
) -> list[dict[str, Any]]:
    """Fetch heart rate summary records."""
    data = _get(
        "/heartRateData",
        params={
            "uploadStartTimeInSeconds": upload_start_ts,
            "uploadEndTimeInSeconds": upload_end_ts,
        },
    )
    return data.get("heartRateData", [])


def fetch_user_id() -> str:
    """Fetch the Garmin user ID for the authenticated user."""
    data = _get("/user/id")
    return str(data.get("userId", ""))
