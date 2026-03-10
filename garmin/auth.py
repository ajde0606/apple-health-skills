"""Garmin Connect OAuth 1.0a token management.

Tokens are persisted to garmin_tokens.json at the repo root (git-ignored).
The Garmin Health API uses three-legged OAuth 1.0a:
  1. Fetch a request token
  2. Redirect user to Garmin authorization page
  3. Exchange the verifier for an access token

References
----------
https://developer.garmin.com/gc-developer-program/overview/
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from requests_oauthlib import OAuth1Session

GARMIN_REQUEST_TOKEN_URL = "https://connectapi.garmin.com/oauth-service/oauth/request_token"
GARMIN_AUTHORIZE_URL = "https://connect.garmin.com/oauthConfirm"
GARMIN_ACCESS_TOKEN_URL = "https://connectapi.garmin.com/oauth-service/oauth/access_token"

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TOKEN_FILE = _REPO_ROOT / "garmin_tokens.json"
_DOTENV_PATH = _REPO_ROOT / ".env"


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


def get_consumer_credentials() -> tuple[str, str]:
    dotenv = _read_dotenv()

    def get(name: str) -> str:
        return os.environ.get(name, dotenv.get(name, ""))

    consumer_key = get("GARMIN_CONSUMER_KEY")
    consumer_secret = get("GARMIN_CONSUMER_SECRET")
    if not consumer_key or not consumer_secret:
        raise RuntimeError(
            "GARMIN_CONSUMER_KEY and GARMIN_CONSUMER_SECRET must be set in .env or environment."
        )
    return consumer_key, consumer_secret


def load_tokens() -> dict[str, Any]:
    if not _TOKEN_FILE.exists():
        return {}
    return json.loads(_TOKEN_FILE.read_text())


def save_tokens(tokens: dict[str, Any]) -> None:
    _TOKEN_FILE.write_text(json.dumps(tokens, indent=2))


def get_request_token(callback_url: str) -> dict[str, str]:
    """Fetch a request token from Garmin.  Returns dict with oauth_token/oauth_token_secret."""
    consumer_key, consumer_secret = get_consumer_credentials()
    oauth = OAuth1Session(consumer_key, client_secret=consumer_secret, callback_uri=callback_url)
    resp = oauth.fetch_request_token(GARMIN_REQUEST_TOKEN_URL)
    return {"oauth_token": resp["oauth_token"], "oauth_token_secret": resp["oauth_token_secret"]}


def build_auth_url(oauth_token: str) -> str:
    """Build the Garmin authorization URL for the user to visit."""
    consumer_key, consumer_secret = get_consumer_credentials()
    oauth = OAuth1Session(consumer_key, client_secret=consumer_secret)
    return oauth.authorization_url(GARMIN_AUTHORIZE_URL, oauth_token)


def exchange_for_access_token(
    oauth_token: str,
    oauth_token_secret: str,
    oauth_verifier: str,
) -> dict[str, Any]:
    """Exchange request token + verifier for a long-lived access token."""
    consumer_key, consumer_secret = get_consumer_credentials()
    oauth = OAuth1Session(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=oauth_token,
        resource_owner_secret=oauth_token_secret,
        verifier=oauth_verifier,
    )
    resp = oauth.fetch_access_token(GARMIN_ACCESS_TOKEN_URL)
    tokens = {
        "oauth_token": resp["oauth_token"],
        "oauth_token_secret": resp["oauth_token_secret"],
    }
    save_tokens(tokens)
    return tokens


def get_oauth_session() -> OAuth1Session:
    """Return an authenticated OAuth1Session using the saved access token."""
    tokens = load_tokens()
    if not tokens:
        raise RuntimeError(
            "No Garmin tokens found. Run 'python scripts/setup_garmin.py' first."
        )
    consumer_key, consumer_secret = get_consumer_credentials()
    return OAuth1Session(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=tokens["oauth_token"],
        resource_owner_secret=tokens["oauth_token_secret"],
    )
