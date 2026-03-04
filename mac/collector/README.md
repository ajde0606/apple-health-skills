# Collector Service (Milestone 1)

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn pydantic
python -m mac.collector.main
```

Environment variables:
- `AHB_INGEST_TOKEN` (default: `dev-token`)
- `AHB_ALLOWED_DEVICES` comma-separated allowlist (default: `dad-iphone`)
- `AHB_DB_PATH` (default: `db/health.db`)

## Endpoints
- `GET /healthz`
- `POST /ingest` with `X-Ingest-Token` header

## Example ingest payload

```json
{
  "batch_id": "batch-001",
  "device_id": "dad-iphone",
  "user_id": "dad",
  "sent_at": 1735863982,
  "samples": [
    {
      "sample_id": "q-001",
      "kind": "quantity",
      "type": "heart_rate",
      "ts": 1735863982,
      "value": 60,
      "unit": "bpm",
      "source": "Apple Watch"
    }
  ]
}
```
