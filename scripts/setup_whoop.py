#!/usr/bin/env python3
"""Interactive OAuth2 setup for the Whoop integration.

Run once to authorize access to your Whoop account:

    python scripts/setup_whoop.py

The script starts a temporary local HTTP server on port 8900 to receive the
OAuth2 redirect, exchanges the code for tokens, and saves them to
whoop_tokens.json at the repo root.

Prerequisites
-------------
1. Create a Whoop developer app at https://developer.whoop.com
2. Set the redirect URI to: http://localhost:8900/callback
3. Add to your .env:
       WHOOP_CLIENT_ID=<your-client-id>
       WHOOP_CLIENT_SECRET=<your-client-secret>
"""
from __future__ import annotations

import http.server
import os
import secrets
import threading
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Allow importing the whoop package from the repo root
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from whoop.auth import build_auth_url, exchange_code

REDIRECT_URI = "http://localhost:8900/callback"
PORT = 8900


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
    code: str | None = None
    state: str | None = None
    error: str | None = None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        _CallbackHandler.error = params.get("error", [None])[0]  # type: ignore[index]
        _CallbackHandler.code = params.get("code", [None])[0]  # type: ignore[index]
        _CallbackHandler.state = params.get("state", [None])[0]  # type: ignore[index]

        if _CallbackHandler.code:
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
    state = secrets.token_urlsafe(16)
    auth_url = build_auth_url(redirect_uri=REDIRECT_URI, state=state)

    server = http.server.HTTPServer(("127.0.0.1", PORT), _CallbackHandler)
    server.timeout = 120  # wait up to 2 minutes for the redirect

    print("\n── Whoop OAuth2 Setup ──────────────────────────────────────")
    print(f"\nOpening browser for authorization…\n  {auth_url}\n")
    print("If the browser did not open, copy the URL above and paste it manually.")
    print("Waiting for redirect to http://localhost:8900/callback …\n")

    # Open browser in a thread so the server can start first
    threading.Timer(0.5, webbrowser.open, args=(auth_url,)).start()

    server.handle_request()  # blocks until one request arrives
    server.server_close()

    if _CallbackHandler.error:
        raise SystemExit(f"OAuth error: {_CallbackHandler.error}")

    if not _CallbackHandler.code:
        raise SystemExit("No authorization code received. Timed out or cancelled.")

    if _CallbackHandler.state != state:
        raise SystemExit("State mismatch — possible CSRF. Aborting.")

    print("Authorization code received. Exchanging for tokens…")
    tokens = exchange_code(code=_CallbackHandler.code, redirect_uri=REDIRECT_URI)

    print("\n✓ Tokens saved to whoop_tokens.json")
    print(f"  access_token expires in {tokens.get('expires_in', '?')}s")
    print("  refresh_token will be used automatically on next sync.\n")
    print("Run 'python scripts/sync_whoop.py' to pull your data.")


if __name__ == "__main__":
    main()
