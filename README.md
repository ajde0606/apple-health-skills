# Apple Health Skills

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
![OpenClaw Skill](https://img.shields.io/badge/OpenClaw-Skill-blue)
![Version](https://img.shields.io/badge/version-v1.0.0-orange)

This repo is an **OpenClaw skill** for live health monitoring. It gives your
OpenClaw agent access to your personal health data so you can build a
**private personal trainer** that knows your body, remembers your history, and
is available whenever you need it — powered entirely by your own data.

Everything runs locally on your Mac. No cloud services, no shared servers, no
accounts beyond what you already have.

**Supported data sources:**

| Source | What it provides |
|--------|-----------------|
| **Apple Health** (Apple Watch / iPhone) | Heart rate, sleep, activity, blood glucose, and all other HealthKit types — synced over your local network |
| **Wahoo HR strap** (or any BLE HR strap) | Live heart-rate streaming during workouts, second by second |
| **Whoop** | Recovery score, HRV, resting HR, sleep performance, strain, and workout zones — pulled from the Whoop Developer API |
| **Garmin** | Daily steps, resting HR, stress level, Body Battery, sleep stages, SpO₂, and activities — pulled from the Garmin Health API |

---

## Contents

1. [Apple Health setup](#apple-health-setup)
   - [Step 1 — iPhone](#step-1--iphone)
   - [Step 2 — Mac](#step-2--mac)
   - [Step 3 — Connect the iOS app](#step-3--connect-the-ios-app)
2. [Whoop setup](#whoop-setup)
3. [Garmin setup](#garmin-setup)
4. [Talk to OpenClaw](#talk-to-openclaw)
5. [Operations toolkit](#operations-toolkit)
6. [Troubleshooting](#troubleshooting)
7. [Environment variables](#environment-variables)

---

## Apple Health setup

Apple Health data is collected by a lightweight FastAPI server running on your
Mac. Your iPhone pushes HealthKit samples to it over HTTPS using the
**IOS Health Bridge** app.

Two network modes are supported:

| Mode | How it works |
|------|-------------|
| **Tailscale Funnel** (default) | Your Mac gets a public HTTPS endpoint — no Tailscale on the iPhone needed |
| **Tailscale VPN** | Classic VPN; iPhone must have Tailscale installed |

### Step 1 — iPhone

Install from the App Store:

| App | Purpose |
|-----|---------|
| **IOS Health Bridge** | Reads HealthKit and uploads to your Mac |

For live workout heart-rate streaming:

| App / Device | Purpose |
|-------------|---------|
| **Wahoo HR sensor** (or compatible BLE HR strap) | Streams live heart rate to IOS Health Bridge |

> **Tailscale is not required on the iPhone** in Funnel mode (the default).
> The iPhone connects to your Mac over the public internet via a secure HTTPS
> URL that Tailscale Funnel provides. Only install Tailscale on the iPhone if
> you specifically choose classic VPN mode during `setup.sh`.

### Step 2 — Mac

#### 2.1 Install Tailscale on Mac

Option A — App Store / download:
- Install from [tailscale.com/download](https://tailscale.com/download)

Option B — Homebrew:

```bash
brew install tailscale
sudo tailscaled
sudo tailscale up
```

**Before running `setup.sh`, enable MagicDNS:**

> 1. Go to [Tailscale admin → DNS](https://login.tailscale.com/admin/dns)
> 2. Toggle **MagicDNS** on

Funnel mode does not need HTTPS Certificates (Tailscale handles TLS at the
edge). Classic VPN mode additionally requires HTTPS Certificates to be enabled.

#### 2.2 Clone, set up environment, and run setup

```bash
git clone https://github.com/your-org/apple-health-skills.git
cd apple-health-skills
```

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then run the interactive setup script:

```bash
bash scripts/setup.sh
```

`setup.sh` will ask you to choose a connectivity mode:

| Mode | Description |
|------|-------------|
| **1 — Tailscale Funnel** (default) | iPhone connects over the internet; no Tailscale on iPhone needed. `tailscale funnel` exposes the collector at `https://<your-mac>.ts.net`. |
| **2 — Tailscale VPN** | Classic mode. iPhone must have Tailscale installed. Traffic stays inside your Tailscale network; requires HTTPS Certificates enabled. |

Then `setup.sh` will:
- Create a Python virtual environment and install dependencies
- Generate a strong random auth token (API key for the collector)
- Configure Tailscale Funnel **or** issue a TLS cert, depending on your choice
- Write everything to a `.env` file (never committed to git)
- Ask for your device ID (find it in the IOS Health Bridge app)

You can also edit `.env` by hand — the only required variables are:

```
AHB_USER_ID=alice
AHB_INGEST_TOKEN=<random secret>
AHB_ALLOWED_DEVICES=iphone-<your device id>
```

For Funnel mode add:

```
AHB_FUNNEL_MODE=true
AHB_PORT=8080
AHB_HOSTNAME=<your-mac>.tail1234.ts.net   # no port — Funnel serves on 443
```

#### 2.3 Start the collector

```bash
bash scripts/start.sh
```

To stop it when running manually:

```bash
bash scripts/stop.sh
```

**Funnel mode:** collector listens on `127.0.0.1:8080` (HTTP); Tailscale
Funnel proxies `https://<your-mac>.ts.net` → `localhost:8080`.

**VPN mode:** collector listens on `0.0.0.0:8443` (HTTPS).

#### 2.4 Verify

**Funnel mode** (test from any device — no Tailscale needed):

```bash
curl https://<your-mac>.ts.net/healthz
# → {"ok":"true","ts":...}
```

**VPN mode** (test from Mac or another Tailscale device):

```bash
# Localhost
curl -sk https://127.0.0.1:8443/healthz

# Via MagicDNS hostname (cert matches, no -k needed)
curl -s https://<tailscale-hostname>:8443/healthz
```

### Step 3 — Connect the iOS app

#### 3.1 Scan the QR code (recommended)

**Funnel mode** — open the QR page on your Mac (only accepts local connections):

```
http://127.0.0.1:8080/qr
```

**VPN mode** — open the QR page via Tailscale IP:

```
https://<tailscale-ip>:8443/qr
```

Then:

1. Open **IOS Health Bridge** on your iPhone → tap the **gear icon** → tap **Scan QR Code**.
2. Point the camera at the QR code. All fields fill in automatically, including the public Funnel URL.

> **HTTPS is always used** in Funnel mode — Tailscale provides it at the edge.
> In VPN mode, `AHB_TLS_CERT`/`AHB_TLS_KEY` must be set; otherwise iOS rejects
> the connection with an App Transport Security error (-1022).

> **Manual setup (fallback):** If you can't use the QR code, tap the gear icon
> and fill in the fields under *Manual Override*: User ID, Collector Host, and
> Auth Token.

#### 3.2 Sync

1. Tap **Authorize HealthKit** and grant read permissions.
2. Tap **Bootstrap Sync (Last 14 Days)** for the initial upload.
3. Tap **Incremental Sync** any time after that.
4. Leave the app installed and backgrounded to receive HealthKit observer updates.
   The app registers background delivery for heart rate, blood glucose, and sleep.

> Background delivery is best-effort on iOS and may arrive minutes to hours
> later. If you force-quit the app from the app switcher, iOS can suppress
> background observer execution until you open the app again.

The app home screen includes a **Sync Logs** panel with timestamped sync
events (authorization, background triggers, queued retries, and upload
outcomes). When running `bash scripts/start.sh`, the collector also prints
timestamped events for startup, `/healthz`, `/qr`, and `/ingest` requests.

#### 3.3 Enable background refresh

On iPhone, allow background app refresh for **IOS Health Bridge** so
background sync delivery can run reliably.

---

## Whoop setup

Whoop data is pulled **directly from the Whoop Developer API** — no iOS app or
Tailscale required. Data is stored in the same local SQLite database alongside
Apple Health data.

### Step 1 — Clone and set up environment

If you haven't cloned the repo yet:

```bash
git clone https://github.com/your-org/apple-health-skills.git
cd apple-health-skills
```

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 2 — Create a developer app

1. Go to [developer.whoop.com](https://developer.whoop.com) and sign in.
2. Create a new app. Set the redirect URI to `http://localhost:8900/callback`.
3. For the Privacy Policy URL, your GitHub repo URL is sufficient for a
   personal app.
4. Copy your **Client ID** and **Client Secret**.

### Step 3 — Add credentials to `.env`

```
WHOOP_CLIENT_ID=<your-client-id>
WHOOP_CLIENT_SECRET=<your-client-secret>
```

### Step 4 — Authorize

```bash
python scripts/setup_whoop.py
```

This opens your browser, walks through the OAuth2 flow, and saves tokens to
`whoop_tokens.json` (git-ignored).

### Step 5 — Sync data

```bash
# Pull the last 30 days for an initial backfill
python scripts/sync_whoop.py --days 30
```

Run this on a schedule (cron or launchd) to keep data fresh:

```bash
# Example crontab entry — sync every morning at 6 AM
0 6 * * * cd /path/to/apple-health-skills && .venv/bin/python scripts/sync_whoop.py --days 2
```

Tokens are refreshed automatically on every sync run.

### Data stored

| Table | Contents |
|-------|----------|
| `whoop_cycles` | Daily strain score, kilojoule, average/max heart rate |
| `whoop_recoveries` | Recovery score (0–100), HRV (RMSSD), resting HR, SpO₂, skin temp |
| `whoop_sleeps` | Sleep performance %, duration, SWS/REM/wake breakdown, respiratory rate |
| `whoop_workouts` | Sport, strain, HR, energy, heart rate zone durations |

---

## Garmin setup

Garmin data is pulled **directly from the Garmin Health API** using OAuth 1.0a
— no iOS app or Tailscale required. Data is stored in the same local SQLite
database alongside Apple Health and Whoop data.

### Step 1 — Clone and set up environment

If you haven't cloned the repo yet:

```bash
git clone https://github.com/your-org/apple-health-skills.git
cd apple-health-skills
```

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 2 — Register as a Garmin Health API developer

1. Go to [developer.garmin.com/gc-developer-program/overview](https://developer.garmin.com/gc-developer-program/overview/) and apply for Health API access.
2. Once approved, create an application to obtain a **Consumer Key** and **Consumer Secret**.

> **Privacy Policy URL:** The application form requires a Privacy Policy URL.
> For a personal/self-hosted setup, your GitHub repo URL is sufficient (e.g.
> `https://github.com/your-username/apple-health-skills`). Garmin does not
> validate the URL for personal developer accounts.
>
> **Approval timeline:** Garmin reviews applications manually. Expect **1–2
> weeks** for approval, though it can take up to 4 weeks during busy periods.
> You will receive an email when your application is approved or if additional
> information is needed.

### Step 3 — Add credentials to `.env`

```
GARMIN_CONSUMER_KEY=<your-consumer-key>
GARMIN_CONSUMER_SECRET=<your-consumer-secret>
```

### Step 4 — Authorize

```bash
python scripts/setup_garmin.py
```

This starts a local callback server on port 8901, opens your browser for the
OAuth 1.0a authorization flow, and saves tokens to `garmin_tokens.json`
(git-ignored).

### Step 5 — Sync data

```bash
# Pull the last 30 days for an initial backfill
python scripts/sync_garmin.py --days 30
```

Run this on a schedule (cron or launchd) to keep data fresh:

```bash
# Example crontab entry — sync every morning at 6 AM
0 6 * * * cd /path/to/apple-health-skills && .venv/bin/python scripts/sync_garmin.py --days 2
```

### Data stored

| Table | Contents |
|-------|----------|
| `garmin_daily_summaries` | Steps, distance, active calories, BMR, stress level, Body Battery (charged/drained), average/resting/min/max HR, SpO₂, respiration rate, floors climbed, intensity minutes |
| `garmin_sleeps` | Duration, deep/light/REM/awake breakdown, SpO₂, respiration rate, resting HR |
| `garmin_activities` | Activity type, duration, distance, average/max HR, active calories, speed, pace, elevation gain |

---

## Talk to OpenClaw

Open OpenClaw and ask your agent to use the **apple-health-skills** skill. Then
ask anything about your health data.

Example prompts — Apple Health:

- *"What's my heart rate trend over the last 24 hours?"*
- *"How was my sleep last night? Any patterns worth watching?"*
- *"Alert me if my heart rate goes above 130 bpm — check every 10 seconds."*

Example prompts — Whoop:

- *"What's my Whoop recovery score today and how does it compare to this week?"*
- *"How has my HRV trended over the last 7 days?"*
- *"Summarize last night's sleep from Whoop."*
- *"What was my strain like during yesterday's workout?"*

Example prompts — Garmin:

- *"How many steps did I average this week?"*
- *"What's my Body Battery trend over the last 7 days?"*
- *"How stressed have I been this week according to Garmin?"*
- *"Summarize my sleep from Garmin last night."*
- *"Show me my activities from the past week."*

When needed, OpenClaw runs these queries automatically:

```bash
# Apple Health
python scripts/query_health.py --window-hours 24 --sleep-nights 7

# Whoop
python scripts/query_whoop.py --window-days 7

# Garmin
python scripts/query_garmin.py --window-days 7
```

You can also run them manually at any time.

---

## Operations toolkit

### Install collector as a LaunchAgent

```bash
bash scripts/install_launch_agent.sh
```

This installs and loads `~/Library/LaunchAgents/com.applehealthbridge.collector.plist`.

To stop and unload the service later:

```bash
bash scripts/stop.sh
```

### Admin CLI

```bash
# Rotate ingest token and update .env
python scripts/admin_cli.py rotate-token

# Show latest successful sync + sample counts
python scripts/admin_cli.py last-sync

# Export last 7 days for debugging
python scripts/admin_cli.py export-json --days 7 --output exports/health_export_last7d.json

# Purge old data (keep only last 90 days)
python scripts/admin_cli.py purge --days 90
```

| Command | What it does |
|---------|-------------|
| `rotate-token` | Generates a new random ingest token, updates `.env`. Existing iOS installs use the old token until you rescan the QR code. Restart the collector after rotating. |
| `last-sync` | Reports the most recent ingest batch (`batch_id`, `device_id`, `received_at`) and current row counts for `quantity_samples` and `category_samples`. |
| `export-json` | Exports a time-windowed snapshot to JSON with `quantity_samples`, `category_samples`, and `ingest_batches` sections. Creates the output directory automatically. |
| `purge` | Deletes rows older than `--days` from `quantity_samples`, `category_samples`, and `ingest_batches`. Destructive — export first if you need the history. |

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `/qr` shows an error page | `AHB_USER_ID` is not set in `.env` — add it and restart the collector |
| "Unrecognised QR code" on iPhone | You scanned something other than the `/qr` endpoint; try again |
| `NSURLErrorDomain Code=-1022` (ATS) | VPN mode: collector serving plain HTTP — run `setup.sh` → choose mode 1 (Funnel) or issue a `tailscale cert` |
| `account does not support getting TLS certs` | VPN mode only. HTTPS Certificates disabled — go to [Tailscale admin → DNS](https://login.tailscale.com/admin/dns), enable **HTTPS Certificates**, re-run `setup.sh` |
| `tailscale funnel` fails | Enable MagicDNS at [Tailscale admin → DNS](https://login.tailscale.com/admin/dns); ensure your plan supports Funnel; run `tailscale funnel 8080` manually |
| Funnel URL returns connection refused | Collector not running, or Funnel pointing to wrong port — verify `AHB_PORT=8080` and that `start.sh` shows "Funnel: active" |
| `401 Unauthorized` | Token in iOS app doesn't match `AHB_INGEST_TOKEN` in `.env` — rescan QR code after restart |
| `403 Forbidden` | Device ID not in `AHB_ALLOWED_DEVICES` — copy it from Settings and add to `.env` |
| `curl: (6) Could not resolve host` | MagicDNS not enabled — go to [Tailscale admin → DNS](https://login.tailscale.com/admin/dns) and toggle **MagicDNS** on |
| iOS can't reach collector (Funnel) | Check `tailscale funnel status`; verify `start.sh` shows "Funnel: active"; test with `curl https://<hostname>/healthz` |
| iOS can't reach collector (VPN) | Confirm both devices show as connected in `tailscale status`; verify MagicDNS is on; verify `start.sh` shows HTTPS as enabled |
| No data in query | Check `--user-id` matches `AHB_USER_ID`; confirm sync completed |
| Empty health data | Grant HealthKit permissions; Health app must have data for selected types |

---

## Environment variables

### Apple Health collector

| Variable | Description |
|----------|-------------|
| `AHB_USER_ID` | Short user identifier (e.g. `alice`) — namespaces all DB rows |
| `AHB_INGEST_TOKEN` | Random secret — must match iOS app Auth Token |
| `AHB_ALLOWED_DEVICES` | Comma-separated device IDs allowed to ingest |
| `AHB_DB_PATH` | Path to SQLite database (default `db/health.db`) |
| `AHB_FUNNEL_MODE` | `true` = Tailscale Funnel mode; server runs plain HTTP on `AHB_PORT` |
| `AHB_PORT` | Local listener port (default `8080` for Funnel, `8443` for VPN) |
| `AHB_HOSTNAME` | Canonical hostname for QR code URLs (auto-detected from Tailscale if not set) |
| `AHB_TLS_CERT` | Path to TLS certificate file — VPN mode only (issued by `tailscale cert`) |
| `AHB_TLS_KEY` | Path to TLS private key file — VPN mode only |

### Whoop

| Variable | Description |
|----------|-------------|
| `WHOOP_CLIENT_ID` | OAuth2 client ID from developer.whoop.com |
| `WHOOP_CLIENT_SECRET` | OAuth2 client secret |

### Garmin

| Variable | Description |
|----------|-------------|
| `GARMIN_CONSUMER_KEY` | OAuth 1.0a consumer key from the Garmin developer portal |
| `GARMIN_CONSUMER_SECRET` | OAuth 1.0a consumer secret |
