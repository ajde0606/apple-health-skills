from __future__ import annotations

import uvicorn

from .config import load_settings


if __name__ == "__main__":
    settings = load_settings()
    kwargs: dict = {}
    if settings.funnel_mode:
        # Tailscale Funnel terminates TLS externally and forwards plain HTTP
        # to localhost.  Bind only to loopback so the port is not reachable
        # from the network directly.
        host = "127.0.0.1"
    else:
        host = "0.0.0.0"
        if settings.tls_cert and settings.tls_key:
            kwargs["ssl_certfile"] = settings.tls_cert
            kwargs["ssl_keyfile"] = settings.tls_key
    uvicorn.run("mac.collector.app:app", host=host, port=settings.port, reload=False, **kwargs)
