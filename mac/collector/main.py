from __future__ import annotations

import uvicorn


if __name__ == "__main__":
    uvicorn.run("mac.collector.app:app", host="0.0.0.0", port=8443, reload=False)
