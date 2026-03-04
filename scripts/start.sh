#!/usr/bin/env bash
# start.sh — Start the Apple Health Bridge collector.
# Loads .env and activates the venv, then runs the FastAPI server.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
VENV="$REPO_ROOT/.venv"

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
        TS_WARN="Tailscale is installed but not running. Start it: open -a Tailscale"
    else
        TS_IP=$(tailscale ip -4 2>/dev/null || echo "")
        TS_HOSTNAME=$(tailscale status --self --json 2>/dev/null \
            | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['Self']['DNSName'].rstrip('.'))" \
            2>/dev/null || echo "")
    fi
fi

SCHEME="http"
TLS_OK=false
if [ -n "${AHB_TLS_CERT:-}" ] && [ -n "${AHB_TLS_KEY:-}" ] \
        && [ -f "${AHB_TLS_CERT}" ] && [ -f "${AHB_TLS_KEY}" ]; then
    SCHEME="https"
    TLS_OK=true
fi

echo "Starting Apple Health Bridge collector on port 8443..."
echo "  User:    $AHB_USER_ID"
echo "  Devices: $AHB_ALLOWED_DEVICES"
echo "  DB:      $AHB_DB_PATH"
echo ""

if $TLS_OK; then
    echo "  HTTPS:   enabled (iOS connections will work)"
else
    echo "  HTTPS:   DISABLED — iOS will reject all connections (ATS error -1022)"
    echo "           Fix: enable MagicDNS at https://login.tailscale.com/admin/dns"
    echo "                then re-run: bash scripts/setup.sh"
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
    echo "  QR code (open in browser on this Mac, then scan with iPhone):"
    echo "    $SCHEME://$TS_IP:8443/qr"
    if [ -n "$TS_HOSTNAME" ] && $DNS_OK; then
        echo "    $SCHEME://$TS_HOSTNAME:8443/qr"
    fi
fi
echo ""
exec python -m mac.collector.main
