from __future__ import annotations

import io
import sqlite3
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import qrcode
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response

from .config import Settings, load_settings
from .db import connect, init_db, insert_ingest_batch, upsert_live_events, upsert_samples
from .models import IngestPayload, IngestResult, LiveEventsPayload, LiveEventsResult


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


def log_event(message: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] {message}", flush=True)


@app.on_event("startup")
def startup() -> None:
    settings = load_settings()
    conn = connect(settings.db_path)
    try:
        init_db(conn)
        log_event(f"collector startup complete db={settings.db_path}")
    finally:
        conn.close()


def bearer_auth(
    authorization: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> Settings:
    expected = f"Bearer {settings.ingest_token}"
    if authorization != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
    return settings


@app.get("/qr")
def qr_code(request: Request, settings: Settings = Depends(get_settings)) -> Response:
    """Return a PNG QR code that the iPhone app can scan for one-tap setup."""
    if not settings.user_id:
        return HTMLResponse(
            "<h2>AHB_USER_ID is not set.</h2>"
            "<p>Add <code>AHB_USER_ID=yourname</code> to your <code>.env</code> file and restart the collector.</p>",
            status_code=400,
        )
    if settings.funnel_mode:
        # Tailscale Funnel always serves HTTPS on port 443; the public host
        # has no port suffix.
        scheme = "https"
    else:
        scheme = "https" if (settings.tls_cert and settings.tls_key) else "http"
    # Prefer the canonical Tailscale hostname stored in AHB_HOSTNAME so the QR
    # payload always contains the hostname (not the IP), even when the browser
    # reached this page via the Tailscale IP address.  Fall back to the Host
    # header only when AHB_HOSTNAME is not configured.
    host = settings.hostname or request.headers.get("host", f"localhost:{settings.port}")
    payload = "ahb://configure?" + urlencode({
        "host": host,
        "scheme": scheme,
        "token": settings.ingest_token,
        "user": settings.user_id,
    })
    log_event(f"qr generated host={host} scheme={scheme}")
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@app.get("/healthz")
def healthz() -> dict[str, int | str]:
    log_event("healthz requested")
    return {"ok": "true", "ts": int(time.time())}


@app.post("/ingest", response_model=IngestResult)
def ingest(
    payload: IngestPayload,
    settings: Settings = Depends(auth),
) -> IngestResult:
    log_event(f"ingest received device={payload.device_id} batch={payload.batch_id} samples={len(payload.samples)}")
    if payload.device_id not in settings.allowed_devices:
        log_event(f"ingest rejected device not allowed device={payload.device_id}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="device not allowed")

    conn = connect(settings.db_path)
    try:
        is_new_batch = insert_ingest_batch(conn, payload)
        if not is_new_batch:
            log_event(f"ingest duplicate batch={payload.batch_id}")
            return IngestResult(ok=True, duplicate_batch=True, inserted=0, skipped=len(payload.samples))

        inserted, skipped = upsert_samples(conn, payload)
        log_event(f"ingest stored batch={payload.batch_id} inserted={inserted} skipped={skipped}")
        return IngestResult(ok=True, duplicate_batch=False, inserted=inserted, skipped=skipped)
    except sqlite3.Error as exc:
        log_event(f"ingest sqlite error batch={payload.batch_id} error={exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    finally:
        conn.close()


@app.post("/api/live/events", response_model=LiveEventsResult)
def ingest_live_events(
    payload: LiveEventsPayload,
    settings: Settings = Depends(bearer_auth),
) -> LiveEventsResult:
    if payload.device_id not in settings.allowed_devices:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="device not allowed")
    if payload.events and any(event.session_id != payload.session_id for event in payload.events):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="session_id mismatch")

    conn = connect(settings.db_path)
    try:
        event_dicts = [event.model_dump() for event in payload.events]
        ack_seq = upsert_live_events(conn, payload.session_id, event_dicts)
        log_event(
            f"live events stored session={payload.session_id} device={payload.device_id} "
            f"count={len(payload.events)} ack_seq={ack_seq}"
        )
        return LiveEventsResult(ok=True, ack_seq=ack_seq)
    except sqlite3.Error as exc:
        log_event(f"live events sqlite error session={payload.session_id} error={exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    finally:
        conn.close()
