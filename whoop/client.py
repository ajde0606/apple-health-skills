"""Whoop API client.

Wraps the Whoop Developer API v1 with automatic token refresh and pagination.
"""
from __future__ import annotations

from typing import Any, Generator

import requests

from .auth import get_valid_access_token

BASE_URL = "https://api.prod.whoop.com/developer/v1"


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    token = get_valid_access_token()
    resp = requests.get(
        f"{BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


def _paginate(path: str, params: dict[str, Any] | None = None) -> Generator[dict[str, Any], None, None]:
    """Yield every record from a paginated Whoop collection endpoint."""
    base_params: dict[str, Any] = {"limit": 25, **(params or {})}
    next_token: str | None = None
    while True:
        if next_token:
            base_params["nextToken"] = next_token
        page = _get(path, base_params)
        records = page.get("records", [])
        yield from records
        next_token = page.get("next_token")
        if not next_token:
            break


# ── High-level fetch helpers ─────────────────────────────────────────────────

def fetch_cycles(start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
    """Fetch physiological cycles (daily strain days).

    Args:
        start: ISO-8601 datetime string (e.g. "2024-01-01T00:00:00.000Z")
        end:   ISO-8601 datetime string
    """
    params: dict[str, Any] = {}
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    return list(_paginate("/cycle", params))


def fetch_recovery_for_cycle(cycle_id: int) -> dict[str, Any] | None:
    """Fetch the recovery record for a single cycle.

    Returns None when the cycle has no recovery score yet (Whoop returns 404).
    Recovery is a sub-resource of cycles: GET /v1/cycle/{cycleId}/recovery
    """
    try:
        return _get(f"/cycle/{cycle_id}/recovery")
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return None
        raise


def fetch_recoveries(cycles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fetch recovery records for a list of cycles.

    Whoop does not expose a collection endpoint for recovery; each record must
    be fetched individually via /v1/cycle/{cycleId}/recovery.
    """
    results = []
    for cycle in cycles:
        rec = fetch_recovery_for_cycle(int(cycle["id"]))
        if rec is not None:
            results.append(rec)
    return results


def fetch_sleeps(cycles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fetch sleep records for a list of cycles.

    Sleep is a sub-resource of cycles: GET /v1/cycle/{cycleId}/sleep
    Each cycle has at most one sleep; 404 means the cycle has no sleep yet.
    """
    results = []
    for cycle in cycles:
        try:
            results.append(_get(f"/cycle/{cycle['id']}/sleep"))
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                continue
            raise
    return results


def fetch_workouts(start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
    """Fetch workouts from the collection endpoint GET /v1/activity/workout."""
    params: dict[str, Any] = {}
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    return list(_paginate("/activity/workout", params))


def fetch_profile() -> dict[str, Any]:
    return _get("/user/profile/basic")
