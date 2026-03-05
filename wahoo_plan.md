# plan.md — Add Wahoo BLE Live Streaming to Existing HealthKit→Mac Bridge App (HTTPS via Tailscale)

## Goal
Extend the existing iOS “bridge app” (already syncing HealthKit → Mac) to also:
- Connect to a Wahoo heart rate strap over BLE (standard Heart Rate Profile)
- Stream live HR events to the Mac over **HTTPS via Tailscale**
- Keep the existing HealthKit syncing features unchanged
- No need to write Wahoo data back into HealthKit

Non-goals:
- No cloud dependency (WHOOP/Garmin/etc.)
- No Apple Watch pairing requirements
- No HealthKit storage for BLE HR

---

## High-level Architecture

### Data paths
1) Existing (unchanged):
- HealthKit → iOS Bridge App → HTTPS (Tailscale) → Mac

2) New (to add):
- Wahoo HR strap (BLE) → iOS Bridge App → HTTPS (Tailscale) → Mac

### Components to add in iOS app
- `BLESensorManager` (CoreBluetooth): scan, connect, subscribe, parse HR
- `LiveSessionController`: start/stop session, manage state, buffering, sending
- `LiveUploader` (HTTPS): POST events to Mac endpoint, retry/backoff
- Shared `Event` schema used by both pipelines (HealthKit and BLE), even if HealthKit still uploads via a different route

### Components to add on Mac
- HTTPS endpoint to ingest live events (`/api/live/events`)
- Optional lightweight persistence (append-only log file or sqlite)
- Forwarding hook to your agent (OpenClaw) if needed

---

## Networking Assumptions
- The Mac is reachable from the iPhone via Tailscale MagicDNS, e.g.
  - `https://my-mac.tailnet.ts.net`
- You already have TLS working (either a reverse proxy with certs or a local service behind a TLS terminator).
- Authentication:
  - Use a static API token in header, or mTLS if you already have it.
  - Minimum: `Authorization: Bearer <TOKEN>`.

---

## Event Schema (JSON)
Use a compact schema for HR.

### HR event
```json
{
  "type": "hr",
  "ts": 1710000001.123,
  "value": 146,
  "unit": "bpm",
  "source": {
    "kind": "ble",
    "vendor": "wahoo",
    "device_id": "A1B2C3D4",
    "device_name": "TICKR X"
  },
  "session_id": "E2C9B4B2-8E3F-4D69-9F10-5F4A0A2C1E1B",
  "seq": 42
}
````

Rules:

* `ts`: Unix epoch seconds (Double) using device clock when received
* `seq`: monotonically increasing integer per session (starts at 1)
* `session_id`: UUID per “Start Live Session”
* `value`: integer bpm

Batch uploads:

```json
{ "events": [ ... ] }
```

---

## Mac API Design

### Endpoint

* `POST /api/live/events`
* Headers:

  * `Authorization: Bearer <TOKEN>`
  * `Content-Type: application/json`

### Request body

```json
{
  "session_id": "uuid",
  "device_id": "A1B2C3D4",
  "events": [ {event}, {event} ]
}
```

### Response body

```json
{
  "ok": true,
  "ack_seq": 42
}
```

Ack behavior:

* `ack_seq` is the highest `seq` successfully persisted/processed.
* iOS can drop buffered events up to `ack_seq`.

Persistence on Mac (choose one):

* Easiest: append JSON lines to a file per session
* Better: sqlite table keyed by (session_id, seq) to dedupe automatically

Dedupe rule:

* If (session_id, seq) already exists, ignore.

---

## iOS BLE Implementation Details

### BLE profile

* Heart Rate Service UUID: `180D`
* Heart Rate Measurement Characteristic UUID: `2A37`
* Subscribe to notifications on `2A37`
* Parse bpm from payload per BLE HR spec:

  * First byte flags
  * If flags bit0 == 0 → bpm is UInt8 at byte1
  * If flags bit0 == 1 → bpm is UInt16 at byte1..2 (little endian)

### CoreBluetooth objects

* `CBCentralManager`
* `CBPeripheral`
* Implement:

  * scanning, filtering by service UUID `180D` (preferred)
  * connect & discover services/characteristics
  * `setNotifyValue(true, for: measurementChar)`

### Device selection UX

* Show list of discovered HR devices (name + RSSI)
* Allow user to select one and connect
* Remember last connected device_id to auto-reconnect

---

## Live Session Behavior (iOS)

### Start/stop

* Start:

  * Create `session_id`
  * Reset `seq = 0`
  * Clear buffer
  * Connect BLE device (or reuse existing connection)
  * Begin sending events to Mac
* Stop:

  * Unsubscribe BLE notifications (optional) and/or disconnect
  * Flush buffer
  * Mark session closed locally

### Buffering

Maintain an in-memory ring buffer + optional disk fallback:

* Store last N events (e.g., 2–5 minutes)
* On network failure, keep buffering (bounded)
* When network resumes, send in batches

### Upload cadence

* Collect events and send in batches every 1–2 seconds OR 10 events, whichever first.
* Keep requests small (< ~50KB).

### Retry policy

* On non-2xx or timeout:

  * exponential backoff: 0.5s → 1s → 2s → 4s → 8s (cap 10s)
* Always preserve ordering by `seq`.

### HealthKit pipeline coexistence

* No changes required to HealthKit sync.
* Ensure the live uploader runs independently and doesn’t block HK uploads.

---

## iOS App Permissions & Capabilities

* `NSBluetoothAlwaysUsageDescription` (and/or appropriate Bluetooth usage keys)
* Capabilities:

  * Background Modes → **Uses Bluetooth LE accessories** (enable)
  * Background Modes → **Background fetch** (optional)
    Notes:
* For highest reliability during outdoor runs, recommend keeping the app in foreground while streaming.

---

## Implementation Milestones

### Milestone 0 — Prep

* Identify current project structure and networking layer used for HealthKit uploads
* Add a new module/group: `LiveStreaming/`

Deliverables:

* `Event` model
* `LiveConfig` (Mac base URL, token)
* Basic logging hooks

### Milestone 1 — Mac ingest endpoint

* Implement `POST /api/live/events` with ack + persistence + dedupe
* Add a simple CLI/log viewer (optional)

Acceptance:

* Can curl a batch and see it persisted with correct ack behavior

### Milestone 2 — BLE connectivity

* Implement scanning UI + connect flow
* Subscribe to HR notifications
* Display live bpm on screen

Acceptance:

* Strap connects reliably; bpm updates ~1Hz in UI

### Milestone 3 — Live uploader over HTTPS (Tailscale)

* Implement `LiveUploader` to batch POST events to Mac
* Add buffering + retry + ack-based buffer trimming

Acceptance:

* While strap is streaming, Mac receives and persists sequential events
* Turning off network buffers; restoring network flushes without duplicates

### Milestone 4 — Session UX + robustness

* Add Start/Stop Live Session buttons
* Auto-reconnect to last strap
* Basic health checks:

  * BLE status
  * last ack time
  * buffer size

Acceptance:

* Outdoor simulation: lock phone, switch networks, recover streaming

### Milestone 5 — Integration to agent (optional)

* On Mac, forward events to OpenClaw agent input queue
* Or expose a local websocket/pipe for the agent to consume

Acceptance:

* Agent sees live HR events and can react

---

## Testing Plan

### Unit tests (iOS)

* HR packet parser:

  * UInt8 bpm
  * UInt16 bpm
* Event sequencing and buffering
* Ack trimming logic

### Integration tests

* iPhone + strap + Mac on same tailnet
* Network failure:

  * Airplane mode for 30s → recover
* Duplicate protection:

  * resend same batch → server dedupes

### Field test (outdoor run)

* App in foreground
* Cellular enabled
* Confirm:

  * bpm displayed on phone
  * Mac receives events within ~1–3s
  * minimal gaps

---

## Security Notes

* Require `Authorization: Bearer <TOKEN>` on Mac endpoints
* Prefer allowlist Tailscale IPs or tailnet ACLs
* Log only necessary data (no personal identifiers)

---

## Project File/Code Layout (suggested)

iOS:

* `LiveStreaming/`

  * `Event.swift`
  * `BLESensorManager.swift`
  * `HeartRateParser.swift`
  * `LiveSessionController.swift`
  * `LiveUploader.swift`
  * `LiveConfig.swift`
  * `LiveView.swift` (or your UI framework equivalent)

Mac:

* `server/`

  * `routes_live.py` (or equivalent)
  * `storage.py` (file/sqlite)
  * `auth.py`
  * `agent_bridge.py` (optional)

---

## Acceptance Criteria

* User can connect a Wahoo HR strap in the bridge app
* User can start a live session and see bpm updating
* Mac receives HR events over HTTPS via Tailscale with:

  * ordered `seq`
  * ack-based trimming
  * dedupe on server
* No change/regression to existing HealthKit sync

