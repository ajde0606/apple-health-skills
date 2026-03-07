from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOTENV_PATH = REPO_ROOT / ".env"


def _read_dotenv(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file into a dict."""
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key:
            data[key] = value
    return data


@dataclass(frozen=True)
class Settings:
    ingest_token: str
    allowed_devices: set[str]
    db_path: str
    user_id: str
    tls_cert: str
    tls_key: str
    hostname: str  # canonical Tailscale hostname, e.g. my-mac.tail….ts.net:8443
    funnel_mode: bool  # True → Tailscale Funnel handles TLS; server runs plain HTTP
    port: int  # local listener port (8443 default, 8080 for Funnel mode)


_tailscale_hostname_cache: str | None = None


def _tailscale_hostname(port: int | None = None) -> str:
    """Return the Tailscale hostname from `tailscale status`, or '' on failure.

    When *port* is provided and not 443, appends ':<port>' to the hostname so
    the caller gets a ready-to-use host:port string.  In Funnel mode port is
    443 (handled by Tailscale), so no port suffix is added.

    Successful lookups are cached for the lifetime of the process.
    Failures are *not* cached so a later request can retry.
    """
    global _tailscale_hostname_cache
    if _tailscale_hostname_cache:
        # Re-format for the requested port on each call; cache stores bare name.
        name = _tailscale_hostname_cache
        return name if (port is None or port == 443) else f"{name}:{port}"
    try:
        out = subprocess.check_output(
            ["tailscale", "status", "--self", "--json"],
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        name = json.loads(out)["Self"]["DNSName"].rstrip(".")
        if not name:
            return ""
        _tailscale_hostname_cache = name
    except Exception:
        return ""
    return _tailscale_hostname_cache if (port is None or port == 443) else f"{_tailscale_hostname_cache}:{port}"


def load_settings() -> Settings:
    dotenv = _read_dotenv(DOTENV_PATH)

    def get(name: str, default: str = "") -> str:
        return os.environ.get(name, dotenv.get(name, default))

    token = get("AHB_INGEST_TOKEN", "dev-token")
    allowed = get("AHB_ALLOWED_DEVICES", "")
    db_path = get("AHB_DB_PATH", "db/health.db")
    user_id = get("AHB_USER_ID", "")
    tls_cert = get("AHB_TLS_CERT", "")
    tls_key = get("AHB_TLS_KEY", "")
    funnel_mode = get("AHB_FUNNEL_MODE", "false").lower() in ("1", "true", "yes")
    # Funnel mode: Tailscale terminates TLS on port 443; server binds HTTP on
    # AHB_PORT (default 8080).  Classic mode: server binds HTTPS on 8443.
    default_port = "8080" if funnel_mode else "8443"
    port = int(get("AHB_PORT", default_port))
    # Hostname for QR code / URL construction.
    # Funnel mode: bare hostname (no port — Tailscale serves on 443).
    # Classic mode: hostname:port.
    ts_port = 443 if funnel_mode else port
    hostname = get("AHB_HOSTNAME", "") or _tailscale_hostname(port=ts_port)
    allowed_devices = {item.strip() for item in allowed.split(",") if item.strip()}
    return Settings(
        ingest_token=token,
        allowed_devices=allowed_devices,
        db_path=db_path,
        user_id=user_id,
        tls_cert=tls_cert,
        tls_key=tls_key,
        hostname=hostname,
        funnel_mode=funnel_mode,
        port=port,
    )
