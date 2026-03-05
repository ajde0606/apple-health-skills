# Apple Health Bridge Test Plan

## 1) Collector API health
- Start collector: `bash scripts/start.sh`
- Verify endpoint: `curl -sk https://127.0.0.1:8443/healthz`
- Expected: JSON payload with `ok` and `ts`.

## 2) Ingest idempotency and dedupe
- Run: `pytest tests/test_db_ingest.py tests/test_milestone2.py`
- Expected: all pass; duplicate batch/sample uploads do not duplicate DB rows.

## 3) Coaching-grade feature summaries (Milestone 4)
- Seed data (via iOS sync or test fixtures).
- Run: `python scripts/query_health.py --user-id <id> --window-hours 24 --sleep-nights 7`
- Expected output contains:
  - `quantity` and `sleep` raw windows
  - `features.sleep`, `features.heart`, and `features.glucose`
  - glucose includes `time_in_range_pct`, `variability_stddev`, `spike_count`

## 4) Operations CLI (Milestone 5)
- Rotate token: `python scripts/admin_cli.py rotate-token`
- Last sync: `python scripts/admin_cli.py last-sync`
- Export JSON: `python scripts/admin_cli.py export-json --days 7 --output exports/health_export_last7d.json`
- Retention purge: `python scripts/admin_cli.py purge --days 90`
- Expected: JSON success responses and corresponding file/DB updates.

## 5) LaunchAgent autostart
- Install: `bash scripts/install_launch_agent.sh`
- Validate load: `launchctl list | grep applehealthbridge.collector`
- Expected: service appears in launchctl and logs written to `~/Library/Logs/applehealthbridge-collector.log`.

