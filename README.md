# Apple Health Skills

This repository contains an end-to-end local Apple Health Bridge prototype:

- **iOS app skeleton** to read HealthKit data and upload batches
- **Mac collector service** (FastAPI) to validate/authenticate ingest requests
- **SQLite local store** for raw samples and ingest batch idempotency
- **Query script** for OpenClaw/local analysis workflows

---

## 1) Prerequisites

## Mac / collector side

1. Python 3.10+
2. (Recommended) virtual environment tooling
3. Network path from iPhone to Mac collector (VPN overlay like Tailscale recommended)

## iOS side

1. Xcode 15+
2. iPhone with Health data available
3. Apple Developer signing setup for running on device

---

## 2) Clone and install dependencies

```bash
git clone <your-repo-url>
cd apple-health-skills
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 3) Start the Mac collector

### 3.1 Configure environment variables

```bash
export AHB_INGEST_TOKEN='dev-token'
export AHB_ALLOWED_DEVICES='dad-iphone'
export AHB_DB_PATH='db/health.db'
```

### 3.2 Start the service

```bash
python -m mac.collector.main
```

The service listens on `http://0.0.0.0:8443` by default.

### 3.3 Verify health endpoint

In a second terminal:

```bash
curl -s http://127.0.0.1:8443/healthz
```

Expected: JSON like `{"ok":"true","ts":...}`.

---

## 4) Test ingest API directly (without iOS)

Run this request while collector is running:

```bash
curl -s -X POST http://127.0.0.1:8443/ingest \
  -H 'Content-Type: application/json' \
  -H 'X-Ingest-Token: dev-token' \
  -d '{
    "batch_id": "batch-001",
    "device_id": "dad-iphone",
    "user_id": "dad",
    "sent_at": 1735863982,
    "samples": [
      {
        "sample_id": "sample-001-heart",
        "kind": "quantity",
        "type": "heart_rate",
        "ts": 1735863982,
        "value": 61,
        "unit": "bpm",
        "source": "Apple Watch"
      },
      {
        "sample_id": "sample-001-sleep",
        "kind": "category",
        "type": "sleep_stage",
        "start_ts": 1735820000,
        "end_ts": 1735823600,
        "category": "asleep",
        "source": "iPhone"
      }
    ]
  }'
```

Expected first response: `{"ok":true,"duplicate_batch":false,...}`.

### 4.1 Verify idempotent batch behavior

Send the exact same request again.

Expected second response: `{"ok":true,"duplicate_batch":true,...}`.

---

## 5) Validate SQLite contents and query script

### 5.1 Query with helper script

```bash
python scripts/query_health.py --db db/health.db --user-id dad --window-hours 24 --sleep-nights 7 --types heart_rate,glucose
```

Expected:

- `quantity.heart_rate` should include your ingested heart-rate sample
- `sleep` should include the sleep segment row

### 5.2 Optional raw SQLite checks

```bash
sqlite3 db/health.db 'select count(*) from ingest_batches;'
sqlite3 db/health.db 'select count(*) from quantity_samples;'
sqlite3 db/health.db 'select count(*) from category_samples;'
```

---

## 6) Run automated tests

```bash
pytest -q
```

This validates DB batch idempotency and sample dedupe behavior.

---

## 7) Set up iOS app and test HealthKit sync

The Swift source is under `ios/HealthBridgeApp/HealthBridgeApp`.

### 7.1 Create and configure Xcode app target

1. Create an iOS SwiftUI app target named **HealthBridgeApp**.
2. Copy all `.swift` files from `ios/HealthBridgeApp/HealthBridgeApp/` into the target.
3. Add `NSHealthShareUsageDescription` to `Info.plist`.
4. Enable **HealthKit** capability.
5. (Milestone 3 later) enable background modes as needed.

### 7.2 Point app to your collector

Edit `ios/HealthBridgeApp/HealthBridgeApp/AppConfig.swift`:

- `collectorURL` → your reachable Mac URL (often VPN DNS name)
- `ingestToken` → same as `AHB_INGEST_TOKEN`
- `deviceID` → include this value in `AHB_ALLOWED_DEVICES`
- `userID` as desired

### 7.3 Run iOS flow on device

1. Launch app
2. Tap **Authorize HealthKit** and grant read permissions
3. Tap **Bootstrap Sync (Last 14 Days)**
4. Tap **Incremental Sync** after new Health data is created

Expected:

- Status transitions to "Sync complete"
- Collector receives `/ingest` batches
- `db/health.db` tables grow

---

## 8) End-to-end retry queue test (offline/online)

1. Stop collector service.
2. In iOS app, trigger sync (bootstrap or incremental).
3. Confirm sync attempts fail and payloads are queued locally.
4. Start collector again.
5. Trigger another sync.

Expected: queued batches flush and data appears in SQLite.

---

## 9) Security and hardening checklist (before real use)

1. Replace default ingest token with strong random secret.
2. Restrict `AHB_ALLOWED_DEVICES` to known devices only.
3. Run collector behind VPN/private network.
4. Add TLS termination/certificates for iPhone-to-Mac transport.
5. Configure launchd/LaunchAgent for always-on collector operation.

---

## 10) Quick troubleshooting

- **401 invalid token**: iOS/`curl` token does not match `AHB_INGEST_TOKEN`.
- **403 device not allowed**: `device_id` missing from `AHB_ALLOWED_DEVICES`.
- **No HealthKit data**: permissions not granted or no samples exist for selected types.
- **No iOS connectivity**: verify VPN/private DNS routing from phone to Mac.
- **Query script empty**: check `--user-id` and time window arguments.
