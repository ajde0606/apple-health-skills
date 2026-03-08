#!/usr/bin/env bash
# setup_oura.sh — Configure the Oura Ring integration
# Run once to add your Oura Personal Access Token and perform an initial data sync.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

echo ""
echo "=== Oura Ring Integration Setup ==="
echo ""

# ── Load existing .env if present ────────────────────────────────────────────
if [[ -f "$ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source <(grep -E '^[A-Z_]+=.' "$ENV_FILE" | sed 's/^/export /')
fi

# ── Oura PAT ──────────────────────────────────────────────────────────────────
if [[ -n "${OURA_PAT:-}" ]]; then
    echo "✓ OURA_PAT already set in .env"
else
    echo "Create a Personal Access Token at:"
    echo "  https://cloud.ouraring.com/personal-access-tokens"
    echo ""
    read -r -p "Paste your Oura Personal Access Token: " OURA_PAT
    if [[ -z "$OURA_PAT" ]]; then
        echo "ERROR: Token cannot be empty." >&2
        exit 1
    fi
    echo "OURA_PAT=$OURA_PAT" >> "$ENV_FILE"
    echo "✓ OURA_PAT saved to .env"
fi

# ── AHB_USER_ID ───────────────────────────────────────────────────────────────
if [[ -n "${AHB_USER_ID:-}" ]]; then
    echo "✓ AHB_USER_ID already set: $AHB_USER_ID"
else
    read -r -p "Enter a user ID (e.g. your name or 'me'): " AHB_USER_ID
    if [[ -z "$AHB_USER_ID" ]]; then
        echo "ERROR: User ID cannot be empty." >&2
        exit 1
    fi
    echo "AHB_USER_ID=$AHB_USER_ID" >> "$ENV_FILE"
    echo "✓ AHB_USER_ID saved to .env"
fi

# ── AHB_DB_PATH ───────────────────────────────────────────────────────────────
AHB_DB_PATH="${AHB_DB_PATH:-db/health.db}"
if ! grep -q "^AHB_DB_PATH=" "$ENV_FILE" 2>/dev/null; then
    echo "AHB_DB_PATH=$AHB_DB_PATH" >> "$ENV_FILE"
fi
DB_ABS="$REPO_ROOT/$AHB_DB_PATH"
mkdir -p "$(dirname "$DB_ABS")"
echo "✓ Database path: $DB_ABS"

# ── OURA_LOOKBACK_DAYS ────────────────────────────────────────────────────────
read -r -p "How many days of history to import? [14]: " LOOKBACK
LOOKBACK="${LOOKBACK:-14}"
if ! grep -q "^OURA_LOOKBACK_DAYS=" "$ENV_FILE" 2>/dev/null; then
    echo "OURA_LOOKBACK_DAYS=$LOOKBACK" >> "$ENV_FILE"
fi

# ── Virtual environment ───────────────────────────────────────────────────────
VENV="$REPO_ROOT/.venv"
if [[ ! -d "$VENV" ]]; then
    echo ""
    echo "Creating Python virtual environment…"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q -r "$REPO_ROOT/requirements.txt"
    echo "✓ Virtual environment ready"
fi
PYTHON="$VENV/bin/python"

# ── Initial sync ──────────────────────────────────────────────────────────────
echo ""
echo "Running initial Oura sync (last $LOOKBACK days)…"
cd "$REPO_ROOT"
"$PYTHON" oura/collector.py --lookback-days "$LOOKBACK"

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  • Query your data:  python scripts/query_oura.py"
echo "  • Re-sync anytime:  python oura/collector.py"
echo "  • Full refresh:     python oura/collector.py --full-refresh"
