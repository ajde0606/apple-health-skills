#!/usr/bin/env bash
# start.sh — Start the Apple Health Bridge collector.
# Loads .env and activates the venv, then runs the FastAPI server.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
VENV="$REPO_ROOT/.venv"

# Ensure local package imports (e.g. `mac.collector.main`) resolve even when
# this script is launched by launchd from a different working directory.
cd "$REPO_ROOT"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: .env not found. Run 'bash scripts/setup.sh' first."
    exit 1
fi

if [ ! -d "$VENV" ]; then
    echo "ERROR: .venv not found. Run 'bash scripts/setup.sh' first."
    exit 1
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"
# Export each non-comment line from .env
set -o allexport
# shellcheck disable=SC1090
source "$ENV_FILE"
set +o allexport

# ── Connectivity diagnostics ──────────────────────────────────────────────────
TS_IP=""
TS_HOSTNAME=""
TS_WARN=""
if ! command -v tailscale &>/dev/null; then
    TS_WARN="Tailscale is not installed. Download from https://tailscale.com/download"
else
    _TS_STATUS_ERR=$(tailscale status 2>&1 >/dev/null || true)
    if echo "$_TS_STATUS_ERR" | grep -qi "not running\|failed to connect\|is tailscale running"; then
        TS_WARN="Tailscale is installed but not running. Start the Tailscale app on macOS, or run one of these on Linux: sudo systemctl start tailscaled ; sudo service tailscaled start ; sudo tailscaled >/tmp/tailscaled.log 2>&1 & (separate terminal)."
    fi
    if [ -z "$TS_WARN" ]; then
        TS_IP=$(tailscale ip -4 2>/dev/null || echo "")
        TS_HOSTNAME=$(tailscale status --self --json 2>/dev/null \
            | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['Self']['DNSName'].rstrip('.'))" \
            2>/dev/null || echo "")
    fi
fi

SCHEME="http"
TLS_OK=false
TLS_PROBLEM=""
if [ -z "${AHB_TLS_CERT:-}" ] || [ -z "${AHB_TLS_KEY:-}" ]; then
    TLS_PROBLEM="AHB_TLS_CERT/AHB_TLS_KEY are missing in .env"
elif [ ! -f "${AHB_TLS_CERT}" ] || [ ! -f "${AHB_TLS_KEY}" ]; then
    TLS_PROBLEM="AHB_TLS_CERT or AHB_TLS_KEY path does not exist"
else
    SCHEME="https"
    TLS_OK=true
fi

# Kill any existing collector and free port 8443 before starting.
# 1) Unload the launchd agent if it is loaded (it would otherwise restart the process).
_LAUNCHD_LABEL="com.applehealthbridge.collector"
if launchctl list 2>/dev/null | grep -q "$_LAUNCHD_LABEL"; then
    _PLIST="${HOME}/Library/LaunchAgents/${_LAUNCHD_LABEL}.plist"
    launchctl unload "$_PLIST" >/dev/null 2>&1 || true
fi
# 2) Kill any remaining collector process by name.
pkill -f "python -m mac.collector.main" >/dev/null 2>&1 || true
# 3) If something else still holds :8443, kill it too.
if command -v lsof &>/dev/null; then
    _PORT_PID=$(lsof -ti tcp:8443 2>/dev/null || true)
    if [ -n "$_PORT_PID" ]; then
        echo "Freeing port 8443 (pid $_PORT_PID)..."
        kill "$_PORT_PID" 2>/dev/null || true
    fi
fi
# Give the OS a moment to release the socket.
sleep 1

echo "Starting Apple Health Bridge collector on port 8443..."
echo "  User:    $AHB_USER_ID"
echo "  Devices: $AHB_ALLOWED_DEVICES"
echo "  DB:      $AHB_DB_PATH"
echo ""

# If Funnel is configured to proxy plain HTTP to 127.0.0.1:8443 while the
# collector expects HTTPS on 8443, public requests will fail with HTTP 502.
FUNNEL_HTTP_BACKEND=false
if command -v tailscale &>/dev/null; then
    _FUNNEL_STATUS=$(tailscale funnel status 2>/dev/null || true)
    if echo "$_FUNNEL_STATUS" | grep -q "proxy http://127.0.0.1:8443"; then
        FUNNEL_HTTP_BACKEND=true
    fi
fi

if $TLS_OK && $FUNNEL_HTTP_BACKEND; then
    echo "  WARNING: Funnel currently forwards plain HTTP to 127.0.0.1:8443,"
    echo "           but collector TLS is enabled on :8443. This causes HTTP 502."
    echo "  Fix for Funnel mode: remove AHB_TLS_CERT/AHB_TLS_KEY from .env,"
    echo "                       restart collector, then re-run: tailscale funnel --bg 8443"
    echo "  (Funnel already provides public HTTPS.)"
    echo ""
fi

if $TLS_OK; then
    echo "  HTTPS:   enabled (iOS connections will work)"
else
    echo "  HTTPS:   DISABLED — iOS will reject all connections (ATS error -1022)"
    echo "  Reason:  $TLS_PROBLEM"
    echo "  Fix:     enable HTTPS by setting valid AHB_TLS_CERT and AHB_TLS_KEY in .env"
    echo "           (Optional helper: enable MagicDNS + HTTPS certs in Tailscale admin, then run: bash scripts/setup.sh)"
    echo ""
fi

if [ -n "$TS_WARN" ]; then
    echo "  Tailscale:  $TS_WARN"
    echo ""
elif [ -n "$TS_IP" ]; then
    # Check whether the MagicDNS hostname resolves on this machine
    DNS_OK=false
    if [ -n "$TS_HOSTNAME" ] && python3 -c "import socket; socket.getaddrinfo('$TS_HOSTNAME', 8443)" &>/dev/null; then
        DNS_OK=true
    fi

    echo "  Tailscale IP:       $TS_IP"
    if [ -n "$TS_HOSTNAME" ]; then
        if $DNS_OK; then
            echo "  Tailscale hostname: $TS_HOSTNAME  (resolves OK)"
        else
            echo "  Tailscale hostname: $TS_HOSTNAME  (DNS NOT resolving yet)"
            echo "    → Enable MagicDNS at https://login.tailscale.com/admin/dns"
            echo "      then re-run: bash scripts/setup.sh  (to issue a cert)"
        fi
    fi
    echo ""
    echo "  Test connectivity from this Mac:"
    echo "    curl -k $SCHEME://$TS_IP:8443/healthz"
    if [ -n "$TS_HOSTNAME" ] && $DNS_OK; then
        echo "    curl    $SCHEME://$TS_HOSTNAME:8443/healthz"
    fi
    echo ""
    echo "  Optional: expose publicly so iPhone does NOT need Tailscale app:"
    echo "    tailscale funnel --bg 8443"
    echo "    tailscale funnel status"
    echo "    (without --bg it exits with Ctrl+C and leaves no active config)"
    echo "    (if you get HTTP 502, disable collector TLS in .env for Funnel mode)"
    echo "    (default Funnel URL is https://<host>/...)"
    echo "    (if client insists on :8443, run: tailscale funnel --bg --https=8443 8443)"
    echo ""
    echo "  QR code (open in browser on this Mac, then scan with iPhone):"
    if $TLS_OK; then
        # TLS cert is bound to the hostname — IP-based URL would cause a
        # hostname-mismatch error (-1200) on iOS. Only show the hostname URL.
        # The /qr endpoint uses AHB_HOSTNAME so the QR payload always contains
        # the hostname even if you access the page via the Tailscale IP.
        if [ -n "$TS_HOSTNAME" ]; then
            echo "    $SCHEME://$TS_IP:8443/qr   ← open this in your browser, then scan"
            echo "    (The QR code will encode the hostname $TS_HOSTNAME, not the IP)"
        else
            echo "    (no Tailscale hostname found — enable MagicDNS and re-run setup.sh)"
            echo "    Enable MagicDNS at https://login.tailscale.com/admin/dns"
        fi
    else
        echo "    $SCHEME://$TS_IP:8443/qr"
        if [ -n "$TS_HOSTNAME" ] && $DNS_OK; then
            echo "    $SCHEME://$TS_HOSTNAME:8443/qr"
        fi
    fi
fi
echo ""
exec python -m mac.collector.main
