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


_tailscale_hostname_cache: str | None = None


def _tailscale_hostname() -> str:
    """Return '<hostname>:8443' from `tailscale status`, or '' on failure.

    Successful lookups are cached for the lifetime of the process.
    Failures are *not* cached so a later request can retry.
    """
    global _tailscale_hostname_cache
    if _tailscale_hostname_cache:
        return _tailscale_hostname_cache
    try:
        out = subprocess.check_output(
            ["tailscale", "status", "--self", "--json"],
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        name = json.loads(out)["Self"]["DNSName"].rstrip(".")
        _tailscale_hostname_cache = f"{name}:8443" if name else ""
    except Exception:
        return ""
    return _tailscale_hostname_cache


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
    hostname = get("AHB_HOSTNAME", "") or _tailscale_hostname()
    allowed_devices = {item.strip() for item in allowed.split(",") if item.strip()}
    return Settings(
        ingest_token=token,
        allowed_devices=allowed_devices,
        db_path=db_path,
        user_id=user_id,
        tls_cert=tls_cert,
        tls_key=tls_key,
        hostname=hostname,
    )
