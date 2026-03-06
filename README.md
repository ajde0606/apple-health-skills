# Apple Health Skill

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
![OpenClaw Skill](https://img.shields.io/badge/OpenClaw-Skill-blue)
![Version](https://img.shields.io/badge/version-v1.0.0-orange)

Stream your iPhone’s Apple Health data to your Mac in real time. 
Your Mac does not need to be on the same Wi-Fi network. Using Tailscale, your 
iPhone can stream Apple Health data securely to your Mac from anywhere in the 
world, as long as the phone has an internet connection. You can use Tailscale 
Funnel so the iPhone app does not need Tailscale installed.

Apple Health Bridge syncs health metrics from **Apple Health / HealthKit** to a
local Mac server, where an AI agent (OpenClaw) can analyze trends, detect
patterns, and provide proactive health insights — **all locally, with no cloud
services or external servers.**

You can also capture **live heart-rate data from a Wahoo strap during workouts**.

```
iPhone ──HealthKit──► IOS Health Bridge app
                              │  (Tailscale VPN)
                              ▼
                     Mac collector (FastAPI)
                              │
                              ▼
                       SQLite (local only)
                              │
                              ▼
               OpenClaw agent  →  alerts & advice
```

---

## Who is this for?

Anyone who wants **private, AI-assisted health monitoring** on their own
machine.

There are:

- no shared servers  
- no accounts to create  
- no cloud services  

Everything runs **locally on your Mac**.

---

## Step 1 — iPhone setup

Install these apps from the App Store:

| App | Purpose |
|-----|---------|
| **IOS Health Bridge** | Reads HealthKit and uploads to your Mac |
| **Tailscale** | Needed on Mac to run the collector and enable Funnel |

With Funnel enabled, **Tailscale is optional on iPhone**.

Optional for live workout heart-rate streaming:

| App / Device | Purpose |
|-----|---------|
| **Wahoo heart-rate sensor** (or compatible BLE HR strap) | Streams live heart rate to IOS Health Bridge |

Sign in to Tailscale with any account (Google, GitHub, Apple, or email).

---

## Step 2 — Mac setup

### 2.1 Install Tailscale on Mac

Use either option below, then sign in on your Mac.

Option A:
- Install from [tailscale.com/download](https://tailscale.com/download)

Option B:

```bash
brew install tailscale
sudo tailscaled
sudo tailscale up # to login
```

**MagicDNS and HTTPS Certificates must be enabled before running `setup.sh`.**

iOS App Transport Security (ATS) blocks all plain HTTP to non-localhost addresses.
The collector must serve HTTPS using a certificate `tailscale cert` issues against
your `.ts.net` hostname — and `tailscale cert` requires MagicDNS to be active.

> **Before running `setup.sh`:**
> 1. Go to [Tailscale admin → DNS](https://login.tailscale.com/admin/dns)
> 2. Toggle **MagicDNS** on
> 3. Toggle **HTTPS Certificates** on

### 2.2 Clone and run setup

```bash
git clone https://github.com/your-org/apple-health-skills.git
cd apple-health-skills
bash scripts/setup.sh
```

> ⚠️ `setup.sh` is a **bash script**, not a Python script. If you run
> `python scripts/setup.sh`, Python will fail with `SyntaxError`.
> If you prefer Python-style invocation, use the compatibility launcher:
> `python scripts/setup.py`.

`setup.sh` will:
- Create a Python virtual environment and install dependencies
- Generate a strong random auth token and API key
- Run `tailscale cert` to issue an HTTPS certificate (required for iOS)
- Write everything to a `.env` file (never committed to git)
- Ask for your device ID (find it in the IOS Health Bridge app)
- Print next steps

You can also edit `.env` by hand — the only required variables are:

```
AHB_USER_ID=alice
AHB_INGEST_TOKEN=<random secret>
AHB_API_KEY=<random secret>
AHB_ALLOWED_DEVICES=iphone-<your device id>
```

### 2.3 Start the collector

```bash
bash scripts/start.sh
```

To stop it when running manually:

```bash
bash scripts/stop.sh
```

The collector listens on port **8443**. Leave this terminal running.

### 2.4 Verify

```bash
# Localhost (always works; -k skips cert hostname check for 127.0.0.1)
curl -sk https://127.0.0.1:8443/healthz
# → {"ok":"true","ts":...}

# Via Tailscale IP (cert is hostname-bound, so -k is needed for IP access)
curl -sk https://<tailscale-ip>:8443/healthz

# Via MagicDNS hostname (no -k needed — cert matches)
curl -s https://<tailscale-hostname>:8443/healthz
```

### 2.5 Expose collector with Tailscale Funnel (no Tailscale app needed on iPhone)

After the collector is running, enable Funnel on port 8443:

```bash
tailscale funnel 8443
```

Get your public Funnel URL:

```bash
tailscale funnel status
```

Use the HTTPS Funnel hostname from that output for iPhone setup (manual override or QR host).
Funnel traffic is public on the internet, so keep both `AHB_INGEST_TOKEN` and `AHB_API_KEY` secret.

---

## Step 3 — Connect the iOS app

### 3.1 Scan the QR code (recommended)

1. On your Mac, open the `/qr` page in a browser:
   ```
   https://<funnel-hostname>/qr  (recommended for no-Tailscale iPhone)
   # or
   https://<tailscale-ip>:8443/qr
   ```
2. Open **IOS Health Bridge** on your iPhone → tap the **gear icon** → tap **Scan QR Code**.
3. Point the camera at the QR code. All fields, including the `https://` scheme, fill in automatically.

> **HTTPS is required.** If the collector is not serving HTTPS (i.e. `AHB_TLS_CERT`/`AHB_TLS_KEY`
> are not set), iOS will reject all connections with an App Transport Security error.
> Run `setup.sh` to issue the certificate automatically.

### 3.2 Sync

1. Tap **Authorize HealthKit** and grant read permissions.
2. Tap **Bootstrap Sync (Last 14 Days)** for the initial upload.
3. Tap **Incremental Sync** any time after that.
4. Leave the app installed and backgrounded to receive HealthKit observer updates.
   The app now registers background delivery for heart rate, blood glucose, and sleep.

> Background delivery is best-effort on iOS and may arrive minutes to hours later.
> If you force-quit the app from the app switcher, iOS can suppress background
> observer execution until you open the app again.
>
> **Manual setup (fallback):** If you can't use the QR code, tap the gear icon
> and fill in the fields under *Manual Override*: User ID, Collector Host,
> Auth Token, and API Key.

The app home screen now includes a **Sync Logs** panel with timestamped sync events
(authorization, background triggers, queued retries, and upload outcomes).
When running `bash scripts/start.sh`, the collector also prints timestamped events
for startup, `/healthz`, `/qr`, and `/ingest` requests.

### 3.4 Enable background refresh

On iPhone, allow background app refresh for **IOS Health Bridge** so background
sync delivery can run reliably.

---

## Step 4 — Talk to OpenClaw

Open OpenClaw, and ask your agent to use the skills apple-health-skills. Then you can ask questions about your health data

Example prompts:

- *"What's my heart rate trend over the last 24 hours?"*
- *"How was my sleep last night? Any patterns worth watching?"*
- *"Alert me if my heart rate goes above 130 bpm — check every 10 secs."*

When needed, OpenClaw can run:

```bash
python scripts/query_health.py --window-hours 24 --sleep-nights 7
```

You can also run that query command manually at any time.

---

## Operations toolkit

### 1. Install collector as a LaunchAgent

```bash
bash scripts/install_launch_agent.sh
```

This installs and loads `~/Library/LaunchAgents/com.applehealthbridge.collector.plist`.

To stop and unload the service later:

```bash
bash scripts/stop.sh
```

### 2. Admin CLI commands

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

`rotate-token` behavior:
- Generates a new random ingest token.
- Updates `AHB_INGEST_TOKEN` in your `.env` file.
- Prints the new token in JSON output.
- Existing iOS app installs will keep using the old token until you update the app settings (or rescan QR).
- Restart the collector after rotating so it definitely picks up the new token.

`last-sync` behavior:
- Reads `ingest_batches` and reports the most recent batch (`batch_id`, `device_id`, `user_id`, `received_at`).
- Prints `latest_sync_iso` as a human-readable UTC timestamp.
- Includes current total row counts for `quantity_samples` and `category_samples`.

`export-json` behavior:
- Exports a time-windowed snapshot (default: last 7 days) to a JSON file.
- Includes three sections: `quantity_samples`, `category_samples`, and `ingest_batches`.
- Creates the output directory automatically if it does not exist.
- Useful for debugging ingest issues without direct SQLite inspection.

`purge` behavior:
- Applies retention by deleting rows older than `--days` from:
  - `quantity_samples` (by `ts`)
  - `category_samples` (by `end_ts`)
  - `ingest_batches` (by `received_at`)
- Prints a JSON summary of how many rows were deleted per table.
- This is destructive; keep a backup/export first if you may need historical data.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `/qr` shows an error page | `AHB_USER_ID` is not set in `.env` — add it and restart the collector |
| "Unrecognised QR code" on iPhone | You scanned something other than the `/qr` endpoint; try again |
| `NSURLErrorDomain Code=-1022` (ATS) | Collector is serving plain HTTP — run `setup.sh` to issue a `tailscale cert` and enable HTTPS |
| `account does not support getting TLS certs` | HTTPS Certificates are disabled on your Tailscale account. Go to [Tailscale admin → DNS](https://login.tailscale.com/admin/dns), scroll to **HTTPS Certificates**, click **Enable**, then re-run `bash scripts/setup.sh` |
| `SyntaxError` when running `python scripts/setup.sh` | Run the setup script with bash instead: `bash scripts/setup.sh` |
| `401 Unauthorized` | Auth Token and/or API Key in iOS app does not match `.env` (`AHB_INGEST_TOKEN`, `AHB_API_KEY`) |
| `403 Forbidden` | Device ID not in `AHB_ALLOWED_DEVICES` — copy it from Settings and add to `.env` |
| `curl: (6) Could not resolve host` | MagicDNS not enabled. Go to [Tailscale admin → DNS](https://login.tailscale.com/admin/dns), toggle **MagicDNS** and **HTTPS Certificates** on, then re-run `bash scripts/setup.sh` to issue the TLS cert. Use `curl -sk https://<tailscale-ip>:8443/healthz` to test by IP in the meantime. |
| iOS can't reach collector | If using Funnel: check `tailscale funnel status` and use the Funnel hostname. If using Tailscale LAN: confirm both devices are connected and MagicDNS is enabled. |
| No data in query | Check `--user-id` matches `AHB_USER_ID`; confirm sync completed |
| Empty health data | Grant HealthKit permissions; Health app must have data for selected types |

## Environment variables (`.env`)

| Variable | Description |
|----------|-------------|
| `AHB_USER_ID` | Short user identifier (e.g. `alice`) — namespaces all DB rows |
| `AHB_INGEST_TOKEN` | Random secret — must match iOS app Auth Token |
| `AHB_ALLOWED_DEVICES` | Comma-separated device IDs allowed to ingest |
| `AHB_API_KEY` | Additional API key required on ingest requests (recommended for Funnel/public exposure) |
| `AHB_DB_PATH` | Path to SQLite database (default `db/health.db`) |
| `AHB_TLS_CERT` | Path to TLS certificate file (issued by `tailscale cert`) |
| `AHB_TLS_KEY` | Path to TLS private key file (issued by `tailscale cert`) |
