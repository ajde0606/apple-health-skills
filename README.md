# Apple Health Bridge

Stream your iPhone's Apple Health data to your Mac in real time. An AI agent
(OpenClaw / Claude Code) monitors it, spots patterns, and gives you proactive
advice — all stored locally, never in the cloud.

```
iPhone ──HealthKit──► AppleHealthBridge app
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

Anyone on a Mac who wants private, AI-assisted health monitoring. There are no
shared servers, no accounts to create, and no cloud services — everything runs
on your own machine.

---

## Step 1 — iPhone setup

Install two apps from the App Store:

| App | Purpose |
|-----|---------|
| **AppleHealthBridge** | Reads HealthKit and uploads to your Mac |
| **Tailscale** | Secure VPN so your iPhone can reach your Mac from anywhere |

Sign in to Tailscale with any account (Google, GitHub, Apple, or email).

---

## Step 2 — Mac setup

### 2.1 Install Tailscale on Mac

Download from [tailscale.com/download](https://tailscale.com/download) and sign
in with the **same** Tailscale account you used on iOS.

**MagicDNS must be enabled before running `setup.sh`.**

iOS App Transport Security (ATS) blocks all plain HTTP to non-localhost addresses.
The collector must serve HTTPS using a certificate `tailscale cert` issues against
your `.ts.net` hostname — and `tailscale cert` requires MagicDNS to be active.

> **Before running `setup.sh`:**
> 1. Go to [Tailscale admin → DNS](https://login.tailscale.com/admin/dns)
> 2. Toggle **MagicDNS** on
> 3. Confirm your Mac's hostname resolves: `curl https://<hostname>:8443/healthz`
>    should reach the collector after it's running

Find your Mac's Tailscale hostname and IP:

```bash
tailscale status --self --json | jq -r .Self.DNSName | tr -d '.'
# → janices-macbook-air.tailcc4114.ts.net  (empty until MagicDNS is on)

tailscale ip -4
# → 100.89.116.78  (always available)
```

`start.sh` will warn you if MagicDNS is not resolving and print the right URLs
to test with.

### 2.2 Clone and run setup

```bash
git clone https://github.com/your-org/apple-health-skills.git
cd apple-health-skills
bash scripts/setup.sh
```

`setup.sh` will:
- Create a Python virtual environment and install dependencies
- Generate a strong random auth token
- Run `tailscale cert` to issue an HTTPS certificate (required for iOS)
- Write everything to a `.env` file (never committed to git)
- Print next steps

You can also edit `.env` by hand — the only required variables are:

```
AHB_USER_ID=alice
AHB_INGEST_TOKEN=<random secret>
AHB_ALLOWED_DEVICES=iphone-<your device id>
```

### 2.3 Start the collector

```bash
bash scripts/start.sh
```

The collector listens on port **8443**. Leave this terminal running (or set up
`launchd` — see [Autostart](#autostart)).

### 2.4 Verify

```bash
# Localhost (always works; -k skips cert hostname check for 127.0.0.1)
curl -sk https://127.0.0.1:8443/healthz
# → {"ok":"true","ts":...}

# Via Tailscale IP (cert is hostname-bound, so -k is needed for IP access)
curl -sk https://100.89.116.78:8443/healthz

# Via MagicDNS hostname (no -k needed — cert matches)
curl -s https://janices-macbook-air.tailcc4114.ts.net:8443/healthz
```

---

## Step 3 — Connect the iOS app

### 3.1 Scan the QR code (recommended)

1. On your Mac, open the `/qr` page in a browser:
   ```
   https://janices-macbook-air.tailcc4114.ts.net:8443/qr
   ```
   (Use your own hostname from `tailscale status --self --json | jq -r .Self.DNSName`.)
2. Open **AppleHealthBridge** on your iPhone → tap the **gear icon** → tap **Scan QR Code**.
3. Point the camera at the QR code. All fields, including the `https://` scheme, fill in automatically.

> **HTTPS is required.** If the collector is not serving HTTPS (i.e. `AHB_TLS_CERT`/`AHB_TLS_KEY`
> are not set), iOS will reject all connections with an App Transport Security error.
> Run `setup.sh` to issue the certificate automatically.

### 3.2 Add your device ID

The app auto-generates a **Device ID** (shown in Settings under *Your Device*).
Copy it and add it to `AHB_ALLOWED_DEVICES` in your Mac's `.env`, then restart
the collector:

```bash
# In .env:
AHB_ALLOWED_DEVICES=iphone-a1b2c3d4

# Then restart:
bash scripts/start.sh
```

### 3.3 Sync

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
> and fill in the fields under *Manual Override*: User ID, Collector Host, and
> Auth Token.

---

## Step 4 — Talk to the agent

Open Claude Code (OpenClaw) in the repo directory:

```bash
cd apple-health-skills
claude
```

The `.env` file is loaded automatically by the query script, so the agent
already knows your user ID and DB path. Ask things like:

- *"What's my heart rate trend over the last 24 hours?"*
- *"How was my sleep last night? Any patterns worth watching?"*
- *"Alert me if my resting HR goes above 90 bpm — check every 30 minutes."*

The agent uses the `openclaw-skill/SKILL.md` skill definition to run:

```bash
python scripts/query_health.py --window-hours 24 --sleep-nights 7
```

You can also run it manually at any time.

---

## Autostart

To keep the collector running 24/7, create a launchd agent:

```bash
# Create ~/Library/LaunchAgents/com.ahb.collector.plist
# (edit paths below to match your actual repo location)

cat > ~/Library/LaunchAgents/com.ahb.collector.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>       <string>com.ahb.collector</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>/YOUR/PATH/apple-health-skills/scripts/start.sh</string>
  </array>
  <key>RunAtLoad</key>   <true/>
  <key>KeepAlive</key>   <true/>
  <key>StandardOutPath</key> <string>/tmp/ahb-collector.log</string>
  <key>StandardErrorPath</key><string>/tmp/ahb-collector.log</string>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.ahb.collector.plist
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `/qr` shows an error page | `AHB_USER_ID` is not set in `.env` — add it and restart the collector |
| "Unrecognised QR code" on iPhone | You scanned something other than the `/qr` endpoint; try again |
| `NSURLErrorDomain Code=-1022` (ATS) | Collector is serving plain HTTP — run `setup.sh` to issue a `tailscale cert` and enable HTTPS |
| `account does not support getting TLS certs` | HTTPS Certificates are disabled on your Tailscale account. Go to [Tailscale admin → DNS](https://login.tailscale.com/admin/dns), scroll to **HTTPS Certificates**, click **Enable**, then re-run `bash scripts/setup.sh` |
| `401 Unauthorized` | Token in iOS app doesn't match `AHB_INGEST_TOKEN` in `.env` |
| `403 Forbidden` | Device ID not in `AHB_ALLOWED_DEVICES` — copy it from Settings and add to `.env` |
| `curl: (6) Could not resolve host` | MagicDNS not enabled. Go to [Tailscale admin → DNS](https://login.tailscale.com/admin/dns), toggle MagicDNS on, then re-run `bash scripts/setup.sh` to issue the TLS cert. Use `curl -sk https://<tailscale-ip>:8443/healthz` to test by IP in the meantime. |
| iOS can't reach collector | Confirm both devices show as connected in `tailscale status`; verify MagicDNS is on; verify `start.sh` shows HTTPS as enabled |
| No data in query | Check `--user-id` matches `AHB_USER_ID`; confirm sync completed |
| Empty health data | Grant HealthKit permissions; Health app must have data for selected types |

---

## Environment variables (`.env`)

| Variable | Description |
|----------|-------------|
| `AHB_USER_ID` | Short user identifier (e.g. `alice`) — namespaces all DB rows |
| `AHB_INGEST_TOKEN` | Random secret — must match iOS app Auth Token |
| `AHB_ALLOWED_DEVICES` | Comma-separated device IDs allowed to ingest |
| `AHB_DB_PATH` | Path to SQLite database (default `db/health.db`) |
| `AHB_TLS_CERT` | Path to TLS certificate file (issued by `tailscale cert`) |
| `AHB_TLS_KEY` | Path to TLS private key file (issued by `tailscale cert`) |

---

## Run tests

```bash
source .venv/bin/activate
pytest -q
```

---

## Architecture

See [architecture.md](architecture.md) for design decisions and data flow details.
