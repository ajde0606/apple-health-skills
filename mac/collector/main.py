from __future__ import annotations

import uvicorn

from .config import load_settings


if __name__ == "__main__":
    settings = load_settings()
    kwargs: dict = {}
    if settings.tls_cert and settings.tls_key:
        kwargs["ssl_certfile"] = settings.tls_cert
        kwargs["ssl_keyfile"] = settings.tls_key
    uvicorn.run("mac.collector.app:app", host="0.0.0.0", port=8443, reload=False, **kwargs)
