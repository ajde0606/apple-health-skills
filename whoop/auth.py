"""Whoop OAuth2 token management.

Tokens are persisted to whoop_tokens.json at the repo root (git-ignored).
The module auto-refreshes the access token when it is expired or within 60s of expiry.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests

WHOOP_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
WHOOP_AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
WHOOP_SCOPES = "offline read:recovery read:cycles read:sleep read:workout read:profile read:body_measurement"

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TOKEN_FILE = _REPO_ROOT / "whoop_tokens.json"
_DOTENV_PATH = _REPO_ROOT / ".env"
_REFRESH_BUFFER_SECONDS = 60


def _read_dotenv() -> dict[str, str]:
    data: dict[str, str] = {}
    if not _DOTENV_PATH.exists():
        return data
    for line in _DOTENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key:
            data[key] = value
    return data


def get_client_credentials() -> tuple[str, str]:
    dotenv = _read_dotenv()

    def get(name: str) -> str:
        return os.environ.get(name, dotenv.get(name, ""))

    client_id = get("WHOOP_CLIENT_ID")
    client_secret = get("WHOOP_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError(
            "WHOOP_CLIENT_ID and WHOOP_CLIENT_SECRET must be set in .env or environment."
        )
    return client_id, client_secret


def load_tokens() -> dict[str, Any]:
    if not _TOKEN_FILE.exists():
        return {}
    return json.loads(_TOKEN_FILE.read_text())


def save_tokens(tokens: dict[str, Any]) -> None:
    _TOKEN_FILE.write_text(json.dumps(tokens, indent=2))


def _is_expired(tokens: dict[str, Any]) -> bool:
    expiry = tokens.get("expires_at", 0)
    return time.time() >= expiry - _REFRESH_BUFFER_SECONDS


def exchange_code(code: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange an authorization code for access + refresh tokens."""
    client_id, client_secret = get_client_credentials()
    resp = requests.post(
        WHOOP_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=15,
    )
    resp.raise_for_status()
    tokens = resp.json()
    tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)
    save_tokens(tokens)
    return tokens


def refresh_tokens(tokens: dict[str, Any]) -> dict[str, Any]:
    """Use the refresh token to obtain a new access token."""
    client_id, client_secret = get_client_credentials()
    resp = requests.post(
        WHOOP_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": WHOOP_SCOPES,
        },
        timeout=15,
    )
    resp.raise_for_status()
    new_tokens = resp.json()
    new_tokens["expires_at"] = time.time() + new_tokens.get("expires_in", 3600)
    save_tokens(new_tokens)
    return new_tokens


def get_valid_access_token() -> str:
    """Return a valid access token, refreshing if necessary."""
    tokens = load_tokens()
    if not tokens:
        raise RuntimeError(
            "No Whoop tokens found. Run 'python scripts/setup_whoop.py' first."
        )
    if _is_expired(tokens):
        tokens = refresh_tokens(tokens)
    return str(tokens["access_token"])


def build_auth_url(redirect_uri: str, state: str = "") -> str:
    """Build the Whoop OAuth2 authorization URL."""
    client_id, _ = get_client_credentials()
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": WHOOP_SCOPES,
        "state": state,
    }
    from urllib.parse import urlencode
    return f"{WHOOP_AUTH_URL}?{urlencode(params)}"
