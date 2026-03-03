# Apple Health Bridge (Dad → Mac → OpenClaw) — Architecture

## 1. Goal

Continuously ingest a user's Apple Health data (heart rate, sleep, glucose, etc.) from their iPhone into a *local* Mac datastore with minutes–hours latency, then expose structured data to an OpenClaw agent for personalized fitness/recovery coaching.

Constraints:
- Health data access must be permissioned via HealthKit on the user's device.
- No “same Wi-Fi only” requirement; should work from anywhere.
- Storage remains local on the Mac (no cloud DB).

## 2. High-level diagram

                       ┌───────────────────────────────────────┐
                       │               OpenClaw                 │
                       │  Agent + Skill (local exec / MCP)      │
                       └───────────────┬───────────────────────┘
                                       │
                                       │ read/query
                                       ▼
┌───────────────────────┐     ┌───────────────────────────────────────┐
│   macOS Collector      │     │          Local Health Store            │
│ (HTTPS ingest server)  │────▶│  SQLite (raw) + derived features cache │
│   + auth + validation  │     │  retention + export utilities          │
└───────────▲───────────┘     └───────────────────────────────────────┘
            │
            │ HTTPS over private network (VPN overlay recommended)
            │
┌───────────┴───────────┐
│   iOS Health Bridge    │
│ (HealthKit reader)     │
│  - permissions         │
│  - incremental sync    │
│  - upload queue        │
└───────────────────────┘

## 3. Network model (not same Wi-Fi)

### Recommended: private VPN overlay
Use an overlay VPN (e.g., Tailscale/WireGuard) so the iPhone can reach the Mac at a stable private hostname/IP from any network (cellular, public Wi-Fi).

Properties:
- No port-forwarding required (typically).
- End-to-end encrypted transport.
- Mac remains “local store of record”.

### Alternative: home VPN server
Run WireGuard/OpenVPN on router/RPi/Mac + DDNS.

Avoid:
- Direct public port forwarding to the Mac collector (higher attack surface).

## 4. Components

### 4.1 iOS Health Bridge App
Responsibilities:
- Request HealthKit READ permissions for selected metrics.
- Bootstrap sync window (e.g., last 14–30 days).
- Incremental sync: detect changes and fetch only new/changed samples.
- Batch uploads to the Mac collector over HTTPS.
- Local retry queue when offline; idempotent resend.

Key HealthKit mechanisms:
- Observer queries to be notified of changes.
- Background delivery where allowed.
- Anchored queries per type to pull deltas and update a persistent anchor.

Important behavioral notes:
- Latency is “minutes–hours”, not guaranteed realtime; iOS may throttle background wakes.
- Sleep often arrives in chunks (after wake/sync).
- Glucose depends on whether the CGM app writes frequent samples to HealthKit.

### 4.2 macOS Collector Service
Responsibilities:
- HTTPS server with `/ingest` endpoint.
- Authenticate requests (token + device allowlist).
- Validate payload schema, timestamp sanity, units.
- Deduplicate via idempotency keys.
- Store into SQLite (raw normalized tables).
- Provide optional read APIs (debug/ops) OR keep reads local via SQLite queries.

Operational requirements:
- Runs 24/7 (LaunchAgent/launchd, or a system service).
- Binds only to VPN interface (recommended).
- Logs + healthcheck endpoint for monitoring.

### 4.3 Local Health Store (SQLite)
Design goals:
- Easy to query by time window and metric type.
- Preserve provenance (source device/app).
- Support upserts/deduplication.
- Separate raw samples from derived features.

Recommended tables:
1) `quantity_samples`
- `id` (TEXT primary key; deterministic hash)
- `user_id` (TEXT)
- `type` (TEXT) e.g., `heart_rate`, `glucose`, `hrv`
- `ts` (INTEGER epoch seconds)
- `value` (REAL)
- `unit` (TEXT) canonicalized (e.g., bpm, mg_dL)
- `source` (TEXT)
- `device` (TEXT nullable)
- `metadata_json` (TEXT nullable)
- `ingested_at` (INTEGER)

2) `category_samples` (sleep, etc.)
- `id` (TEXT primary key)
- `user_id`
- `type` (TEXT) e.g., `sleep_stage`
- `start_ts` (INTEGER)
- `end_ts` (INTEGER)
- `category` (TEXT) e.g., `asleepDeep`, `asleepREM`, `inBed`
- `source`, `device`, `metadata_json`, `ingested_at`

3) `sync_state`
- `user_id`
- `hk_type` (TEXT) or `type_group`
- `anchor_blob` (BLOB/TEXT) stored on iOS; Mac stores server cursor if needed
- `last_seen_ts` (INTEGER)

4) `features_daily` (optional cache)
- `user_id`
- `date` (YYYY-MM-DD)
- `json` (derived stats)

Retention:
- Keep raw samples for N months; archive older to compressed files if needed.

### 4.4 OpenClaw Integration (Skill)
Two viable patterns:

A) Local exec skill reading SQLite (recommended for V0)
- OpenClaw runs `python query_health.py --window 24h --types glucose,heart_rate,sleep`
- Script returns JSON to the agent.

B) MCP server wrapping queries (optional later)
- Local MCP server exposes tools (get_glucose, get_sleep, get_trends).
- OpenClaw uses MCP tool calls.

Tool surface (example):
- `get_latest_vitals(window_minutes=60)`
- `get_sleep(nights=7)`
- `get_glucose(window_hours=24)`
- `get_trends(days=14)`
- `get_recovery_signals(days=14)`

## 5. Data contracts

### 5.1 Ingest request (iOS → Mac)
Endpoint: `POST /ingest`
Headers:
- `Authorization: Bearer <token>`
- `X-Device-Id: <string>`
- `Content-Type: application/json`

Body:
```json
{
  "user_id": "dad",
  "batch_id": "uuid-or-hash",
  "sent_at": "2026-03-03T23:10:00Z",
  "samples": [
    {
      "kind": "quantity",
      "type": "heart_rate",
      "ts": "2026-03-03T23:09:12Z",
      "value": 72.0,
      "unit": "bpm",
      "source": "Apple Watch",
      "device": "Watch",
      "metadata": {}
    },
    {
      "kind": "quantity",
      "type": "glucose",
      "ts": "2026-03-03T23:08:00Z",
      "value": 112.0,
      "unit": "mg_dL",
      "source": "Lingo",
      "device": null,
      "metadata": {}
    },
    {
      "kind": "category",
      "type": "sleep_stage",
      "start": "2026-03-03T06:20:00Z",
      "end": "2026-03-03T06:45:00Z",
      "category": "asleepDeep",
      "source": "Apple Watch",
      "device": "Watch",
      "metadata": {}
    }
  ]
}
Server response:

200 with { "ok": true } if accepted

409 if duplicate batch_id (idempotent success)

401/403 for auth failures

400 for schema validation errors

5.2 Units and normalization

Canonical units:

Heart rate: bpm

Glucose: mg/dL (also store original if needed)

Sleep stages: enumerated strings
All timestamps normalized to UTC ISO8601 in transit, stored as epoch seconds.

6. Security model

Transport: HTTPS only.

Auth: long random bearer token per user/device; rotate periodically.

Network exposure: bind collector to VPN interface only; firewall deny others.

Validation: strict JSON schema + bounds checks.

Privacy: local SQLite encrypted by FileVault; avoid cloud logs.

Least privilege: iOS app requests only READ access to required HealthKit types.

Certificate strategy:

Prefer a real cert in private DNS if using overlay VPN with DNS.

Otherwise use a locally trusted CA and install the CA profile on the iPhone.

Optional: certificate/public-key pinning in the iOS app.

7. Failure modes and mitigations

iOS background throttling: add foreground “Sync now” + periodic background attempts; tolerate minutes–hours.

Mac offline/sleep: keep Mac awake; run as daemon; queue uploads on iOS.

Network unreachable: VPN down; iOS queues and retries with exponential backoff.

Large historical sync: bootstrap with bounded date ranges; batch and compress.

Duplicates/out-of-order: idempotency keys + deterministic sample IDs.

8. Non-goals (explicit)

No medical diagnosis or emergency alerts; coaching is informational.

No access to Apple Health via Apple ID credentials or remote scraping.

No third-party cloud datastore for raw health samples (unless user chooses later).
