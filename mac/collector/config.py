from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Parse a simple KEY=VALUE .env file and set missing env vars."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Don't override values already set in the environment
        if key and key not in os.environ:
            os.environ[key] = value


# Load .env from repo root (two levels up from this file) if present
_load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")


@dataclass(frozen=True)
class Settings:
    ingest_token: str
    allowed_devices: set[str]
    db_path: str
    user_id: str


def load_settings() -> Settings:
    token = os.environ.get("AHB_INGEST_TOKEN", "dev-token")
    allowed = os.environ.get("AHB_ALLOWED_DEVICES", "")
    db_path = os.environ.get("AHB_DB_PATH", "db/health.db")
    user_id = os.environ.get("AHB_USER_ID", "")
    allowed_devices = {item.strip() for item in allowed.split(",") if item.strip()}
    return Settings(
        ingest_token=token,
        allowed_devices=allowed_devices,
        db_path=db_path,
        user_id=user_id,
    )
