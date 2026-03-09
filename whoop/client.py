"""Whoop API client.

Wraps the Whoop Developer API v1 (cycles) and v2 (recovery, sleep, workout)
with automatic token refresh and pagination.
"""
from __future__ import annotations

from typing import Any, Generator

import requests

from .auth import get_valid_access_token

# Cycles are still on v1; recovery/sleep/workout moved to v2.
BASE_URL_V1 = "https://api.prod.whoop.com/developer/v1"
BASE_URL_V2 = "https://api.prod.whoop.com/developer/v2"


def _get(base_url: str, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    token = get_valid_access_token()
    resp = requests.get(
        f"{base_url}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


def _paginate(base_url: str, path: str, params: dict[str, Any] | None = None) -> Generator[dict[str, Any], None, None]:
    """Yield every record from a paginated Whoop collection endpoint."""
    base_params: dict[str, Any] = {"limit": 25, **(params or {})}
    next_token: str | None = None
    while True:
        if next_token:
            base_params["nextToken"] = next_token
        page = _get(base_url, path, base_params)
        records = page.get("records", [])
        yield from records
        next_token = page.get("next_token")
        if not next_token:
            break


# ── High-level fetch helpers ─────────────────────────────────────────────────

def fetch_cycles(start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
    """Fetch physiological cycles via GET /v1/cycle."""
    params: dict[str, Any] = {}
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    return list(_paginate(BASE_URL_V1, "/cycle", params))


def fetch_recoveries(start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
    """Fetch recovery records via GET /v2/recovery."""
    params: dict[str, Any] = {}
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    return list(_paginate(BASE_URL_V2, "/recovery", params))


def fetch_sleeps(start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
    """Fetch sleep records via GET /v2/activity/sleep."""
    params: dict[str, Any] = {}
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    return list(_paginate(BASE_URL_V2, "/activity/sleep", params))


def fetch_workouts(start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
    """Fetch workout records via GET /v2/activity/workout."""
    params: dict[str, Any] = {}
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    return list(_paginate(BASE_URL_V2, "/activity/workout", params))


def fetch_profile() -> dict[str, Any]:
    return _get(BASE_URL_V1, "/user/profile/basic")
