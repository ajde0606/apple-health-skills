from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    ingest_token: str
    allowed_devices: set[str]
    db_path: str



def load_settings() -> Settings:
    token = os.environ.get("AHB_INGEST_TOKEN", "dev-token")
    allowed = os.environ.get("AHB_ALLOWED_DEVICES", "dad-iphone")
    db_path = os.environ.get("AHB_DB_PATH", "db/health.db")
    allowed_devices = {item.strip() for item in allowed.split(",") if item.strip()}
    return Settings(ingest_token=token, allowed_devices=allowed_devices, db_path=db_path)
