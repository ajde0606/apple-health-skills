#!/usr/bin/env python3
"""Interactive OAuth 1.0a setup for the Garmin Connect integration.

Run once to authorize access to your Garmin account:

    python scripts/setup_garmin.py

The script starts a temporary local HTTP server on port 8901 to receive the
OAuth 1.0a callback, exchanges the verifier for an access token, and saves
it to garmin_tokens.json at the repo root.

Prerequisites
-------------
1. Register as a Garmin Health API developer at https://developer.garmin.com/gc-developer-program/overview/
2. Create an application to obtain a consumer key and secret.
3. Add to your .env:
       GARMIN_CONSUMER_KEY=<your-consumer-key>
       GARMIN_CONSUMER_SECRET=<your-consumer-secret>
"""
from __future__ import annotations

import http.server
import os
import threading
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from garmin.auth import build_auth_url, exchange_for_access_token, get_request_token

CALLBACK_URL = "http://localhost:8901/callback"
PORT = 8901


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


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    oauth_token: str | None = None
    oauth_verifier: str | None = None
    error: str | None = None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        _CallbackHandler.error = params.get("error", [None])[0]  # type: ignore[index]
        _CallbackHandler.oauth_token = params.get("oauth_token", [None])[0]  # type: ignore[index]
        _CallbackHandler.oauth_verifier = params.get("oauth_verifier", [None])[0]  # type: ignore[index]

        if _CallbackHandler.oauth_verifier:
            body = b"<h2>Authorization successful!</h2><p>You can close this tab.</p>"
        else:
            body = b"<h2>Authorization failed.</h2><p>Check the terminal for details.</p>"

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:  # suppress server logs
        pass


def main() -> None:
    print("\n── Garmin OAuth 1.0a Setup ─────────────────────────────────")
    print("\nFetching request token from Garmin…")

    request_token = get_request_token(callback_url=CALLBACK_URL)
    oauth_token = request_token["oauth_token"]
    oauth_token_secret = request_token["oauth_token_secret"]

    auth_url = build_auth_url(oauth_token=oauth_token)

    server = http.server.HTTPServer(("127.0.0.1", PORT), _CallbackHandler)
    server.timeout = 120  # wait up to 2 minutes for the redirect

    print(f"\nOpening browser for authorization…\n  {auth_url}\n")
    print("If the browser did not open, copy the URL above and paste it manually.")
    print("Waiting for redirect to http://localhost:8901/callback …\n")

    threading.Timer(0.5, webbrowser.open, args=(auth_url,)).start()

    server.handle_request()  # blocks until one request arrives
    server.server_close()

    if _CallbackHandler.error:
        raise SystemExit(f"OAuth error: {_CallbackHandler.error}")

    if not _CallbackHandler.oauth_verifier:
        raise SystemExit("No OAuth verifier received. Timed out or cancelled.")

    print("Verifier received. Exchanging for access token…")
    tokens = exchange_for_access_token(
        oauth_token=oauth_token,
        oauth_token_secret=oauth_token_secret,
        oauth_verifier=_CallbackHandler.oauth_verifier,
    )

    print("\n✓ Tokens saved to garmin_tokens.json")
    print(f"  oauth_token: {tokens['oauth_token'][:12]}…")
    print("Run 'python scripts/sync_garmin.py' to pull your data.\n")


if __name__ == "__main__":
    main()
