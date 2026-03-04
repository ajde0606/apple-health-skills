from __future__ import annotations

import io
import sqlite3
import time
from urllib.parse import urlencode

import qrcode
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response

from .config import Settings, load_settings
from .db import connect, init_db, insert_ingest_batch, upsert_samples
from .models import IngestPayload, IngestResult


def get_settings() -> Settings:
    return load_settings()


def auth(
    x_ingest_token: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> Settings:
    if x_ingest_token != settings.ingest_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
    return settings


app = FastAPI(title="Apple Health Bridge Collector", version="0.1.0")


@app.on_event("startup")
def startup() -> None:
    settings = load_settings()
    conn = connect(settings.db_path)
    try:
        init_db(conn)
    finally:
        conn.close()


@app.get("/qr")
def qr_code(request: Request, settings: Settings = Depends(get_settings)) -> Response:
    """Return a PNG QR code that the iPhone app can scan for one-tap setup."""
    if not settings.user_id:
        return HTMLResponse(
            "<h2>AHB_USER_ID is not set.</h2>"
            "<p>Add <code>AHB_USER_ID=yourname</code> to your <code>.env</code> file and restart the collector.</p>",
            status_code=400,
        )
    host = request.headers.get("host", "localhost:8443")
    scheme = "https" if (settings.tls_cert and settings.tls_key) else "http"
    payload = "ahb://configure?" + urlencode({
        "host": host,
        "scheme": scheme,
        "token": settings.ingest_token,
        "user": settings.user_id,
    })
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@app.get("/healthz")
def healthz() -> dict[str, int | str]:
    return {"ok": "true", "ts": int(time.time())}


@app.post("/ingest", response_model=IngestResult)
def ingest(
    payload: IngestPayload,
    settings: Settings = Depends(auth),
) -> IngestResult:
    if payload.device_id not in settings.allowed_devices:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="device not allowed")

    conn = connect(settings.db_path)
    try:
        is_new_batch = insert_ingest_batch(conn, payload)
        if not is_new_batch:
            return IngestResult(ok=True, duplicate_batch=True, inserted=0, skipped=len(payload.samples))

        inserted, skipped = upsert_samples(conn, payload)
        return IngestResult(ok=True, duplicate_batch=False, inserted=inserted, skipped=skipped)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    finally:
        conn.close()
