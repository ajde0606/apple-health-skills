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

echo "Starting Apple Health Bridge collector on port 8443..."
echo "  User:    $AHB_USER_ID"
echo "  Devices: $AHB_ALLOWED_DEVICES"
echo "  DB:      $AHB_DB_PATH"
echo ""
exec python -m mac.collector.main
