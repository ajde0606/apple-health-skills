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


_DEBUG_PRINTED: set[str] = set()


def _debug_404(label: str, url: str, exc: requests.HTTPError) -> None:
    """Print the response body for the first 404 of each endpoint type."""
    if label not in _DEBUG_PRINTED:
        _DEBUG_PRINTED.add(label)
        body = exc.response.text if exc.response is not None else "(no response)"
        print(f"\n  [debug] First {label} 404 → {url}\n  body: {body[:300]}", flush=True)


def _warn_if_scope_issue(kind: str, not_found: int, total: int) -> None:
    """Print a warning when most/all cycles return 404 for a data type.

    This pattern almost always means the OAuth token lacks the required scope
    (Whoop returns 404, not 403, for unauthorized scopes).
    """
    if total > 0 and not_found == total:
        print(
            f"\n  WARNING: All {total} {kind} requests returned 404. "
            "This usually means your token is missing the required OAuth scope. "
            "Re-run 'python scripts/setup_whoop.py' to re-authorize with all scopes.",
            flush=True,
        )


def fetch_recoveries(cycles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fetch recovery records for a list of cycles via /v1/cycle/{cycleId}/recovery.

    Also prints the first cycle id so the constructed path is visible in debug output.
    """
    if cycles:
        print(f"\n  [debug] First cycle id={cycles[0]['id']} → will call {BASE_URL}/cycle/{cycles[0]['id']}/recovery", flush=True)
    results: list[dict[str, Any]] = []
    not_found = 0
    for cycle in cycles:
        path = f"/cycle/{cycle['id']}/recovery"
        try:
            results.append(_get(path))
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                _debug_404("recovery", f"{BASE_URL}{path}", exc)
                not_found += 1
                continue
            raise
    _warn_if_scope_issue("recovery", not_found, len(cycles))
    return results


def fetch_sleeps(cycles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fetch sleep records for a list of cycles via /v1/cycle/{cycleId}/sleep."""
    results: list[dict[str, Any]] = []
    not_found = 0
    for cycle in cycles:
        path = f"/cycle/{cycle['id']}/sleep"
        try:
            results.append(_get(path))
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                _debug_404("sleep", f"{BASE_URL}{path}", exc)
                not_found += 1
                continue
            raise
    _warn_if_scope_issue("sleep", not_found, len(cycles))
    return results


def fetch_workouts(cycles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fetch workout records for a list of cycles via /v1/cycle/{cycleId}/workout."""
    results: list[dict[str, Any]] = []
    not_found = 0
    for cycle in cycles:
        path = f"/cycle/{cycle['id']}/workout"
        try:
            data = _get(path)
            if isinstance(data, list):
                results.extend(data)
            elif isinstance(data, dict):
                records = data.get("records") or data.get("workouts")
                if records is not None:
                    results.extend(records)
                else:
                    results.append(data)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                _debug_404("workout", f"{BASE_URL}{path}", exc)
                not_found += 1
                continue
            raise
    _warn_if_scope_issue("workout", not_found, len(cycles))
    return results


def fetch_profile() -> dict[str, Any]:
    return _get("/user/profile/basic")
