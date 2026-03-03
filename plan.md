
---

# plan.md

```markdown
# Apple Health Bridge — Implementation Plan

## 0. Success criteria
- Works from anywhere (not same Wi-Fi).
- Ingest latency typically minutes–hours.
- Local-only storage on Mac.
- OpenClaw can query HR, sleep, glucose for coaching prompts.

## 1. Milestones (recommended order)

### Milestone 1 — End-to-end MVP (manual sync)
Goal: prove the pipeline works with minimal background complexity.

Deliverables:
1) macOS Collector (HTTPS + token auth)
- `/ingest` endpoint
- SQLite write path
- basic logs + healthcheck

2) iOS app (foreground-only)
- HealthKit permission UI
- “Sync last N days now” button
- Pull sample types and POST to collector
- Local queue + retry while app is open

3) OpenClaw skill (SQLite read)
- `query_health.py` that returns JSON windows for:
  - last 60 minutes heart rate samples (or summary)
  - last 24 hours glucose samples
  - last 7 nights sleep segments
- Agent prompt template: daily summary + suggested training intensity

Exit test:
- Perform a manual sync; confirm SQLite tables filled.
- Run OpenClaw tool; confirm it returns correct JSON.

### Milestone 2 — Incremental sync (anchors) + dedupe
Goal: avoid re-sending whole history; make sync efficient.

Deliverables:
- Anchored queries per metric type with persistent anchor storage on iOS:
  - per-type anchor saved in app storage (Keychain/UserDefaults)
- Deterministic `sample_id` creation (hash of type + ts + value + source + start/end)
- Server idempotency:
  - accept duplicate sample IDs without duplication
  - accept duplicate batch IDs as no-op success

Exit test:
- Sync N days, then add new data, sync again; only new samples appear.

### Milestone 3 — Background delivery (minutes–hours)
Goal: get near real-time without user interaction.

Deliverables:
- Register observer queries for selected types at app launch.
- Enable background delivery for those types (where permitted).
- In observer handler:
  - trigger anchored query to fetch deltas
  - enqueue upload batch
  - call completion handler quickly
- Background task handling:
  - use background processing/time-limited execution to upload quickly
  - if upload fails, persist queue for later

Exit test:
- With app not in foreground, new HR/glucose sample appears; within minutes/hours Mac receives it.
- If user force-quits app, document expected behavior (background may not run).

### Milestone 4 — Coaching-grade features
Goal: produce better advice than raw sample dumping.

Deliverables:
Compute daily / rolling features on Mac (in a cron job or on query):
- Sleep:
  - total sleep time, time in bed, efficiency
  - stage totals (deep/REM/light) when available
  - consistency (bed/wake variance)
- Heart:
  - resting HR trend, median HR, HRV trend (if enabled)
- Glucose:
  - time in range, mean, variability (stddev), spike counts
  - overnight baseline estimate

Store in `features_daily` and/or compute on demand.

Exit test:
- OpenClaw tool returns both raw + feature summaries.
- Agent produces consistent, personalized suggestions.

### Milestone 5 — Operations + UX polish
Deliverables:
- Mac LaunchAgent/launchd service install
- Simple admin CLI:
  - rotate token
  - show last sync time
  - export last 7 days to JSON for debugging
- Retention policy and purge command
- Optional: local dashboard (later)

## 2. Detailed work plan

### 2.1 macOS Collector
Tech choice (pick one):
- Python FastAPI + uvicorn, or
- Node (Express/Fastify)

Required features:
- TLS termination
- Auth middleware
- JSON schema validation
- SQLite writer

Implementation steps:
1) Define JSON schema for ingest payload.
2) Implement `/ingest`:
   - verify token
   - verify device allowlist
   - validate payload
   - upsert into SQLite
3) Add `/healthz` and structured logs.
4) Bind to VPN interface only; configure firewall.

TLS strategy:
- If VPN overlay provides DNS, generate cert for that name.
- Otherwise create a local CA and install CA profile on iPhone.

### 2.2 iOS Health Bridge
Implementation steps:
1) HealthKit permission screen:
   - request only required types
2) Bootstrap sync:
   - query last N days for each type
   - batch results (size limit per request)
3) Incremental sync:
   - store anchor per type
   - anchored query returns “added” and “deleted” (handle deletes as tombstones if needed)
4) Background:
   - set up observer queries at launch
   - enable background delivery entitlement/config
   - implement observer callback to run anchored query + upload
5) Upload queue:
   - persistent queue on disk
   - exponential backoff
   - idempotency via batch_id and sample_id

### 2.3 Local DB + query scripts
Steps:
1) Create SQLite schema + indices:
   - index on (user_id, type, ts)
2) Implement query script(s):
   - `query_health.py`:
     - returns raw windows + precomputed features
     - supports `--types`, `--since`, `--until`, `--days`
3) Optional: feature computation job:
   - scheduled every hour/day
   - updates `features_daily`

### 2.4 OpenClaw Skill
Deliverables:
- `SKILL.md` with usage instructions
- A tool entry that runs:
  - `python query_health.py ...`
- Output JSON contract stable and documented.

Agent prompt conventions:
- Always cite which windows were used (e.g., “sleep last 7 nights”).
- Keep language informational, not medical.
- If extreme values detected, advise contacting a clinician.

## 3. Testing strategy

### Unit tests
- Payload validation
- Unit conversion
- sample_id determinism
- SQLite upsert behavior

### Integration tests
- iOS manual sync → Mac ingest → SQLite query
- offline queue + retry
- dedupe/idempotency on repeated posts

### Load tests
- Bootstrap 30 days with high-frequency samples; ensure batching and performance.

## 4. Risks & mitigations
- Background delivery is not guaranteed:
  - mitigate with periodic foreground “Sync now”, and scheduled background attempts.
- Certificate management complexity:
  - start with VPN overlay + DNS + proper cert, or install local CA profile.
- Glucose availability:
  - verify that the glucose app writes to HealthKit at desired frequency.
- Privacy/security:
  - strict least-privilege permissions, local storage, minimal logging.

## 5. Decisions to lock early
1) Connectivity:
   - VPN overlay (recommended) vs home VPN vs port-forwarding (avoid)
2) TLS approach:
   - cert on VPN DNS name vs local CA profile
3) Initial metric set:
   - HR + sleep + glucose minimum; add HRV/resting HR/workouts later
4) Query surface for OpenClaw:
   - SQLite direct first; MCP server later if needed

## 6. Suggested repo layout
repo/
docs/
architecture.md
plan.md
ios/
HealthBridgeApp/
mac/
collector/
db/
scripts/
query_health.py
openclaw-skill/
SKILL.md
tools/
