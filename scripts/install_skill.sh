#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_SKILL_DIR="$REPO_ROOT/openclaw-skill"
SRC_QUERY_SCRIPT="$REPO_ROOT/scripts/query_health.py"

DEST_ROOT="${CODEX_HOME:-$HOME/.codex}/skills"
SKILL_NAME="apple-health-query"
DEST_SKILL_DIR="$DEST_ROOT/$SKILL_NAME"

usage() {
  cat <<USAGE
Install the Apple Health Query skill into Codex local skills.

Usage:
  bash scripts/install_skill.sh [--dest-root <path>] [--force]

Options:
  --dest-root <path>  Override destination root (default: \$CODEX_HOME/skills or ~/.codex/skills)
  --force             Replace existing installed skill directory
  -h, --help          Show this message
USAGE
}

FORCE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dest-root)
      [[ $# -ge 2 ]] || { echo "ERROR: --dest-root requires a value" >&2; exit 2; }
      DEST_ROOT="$2"
      DEST_SKILL_DIR="$DEST_ROOT/$SKILL_NAME"
      shift 2
      ;;
    --force)
      FORCE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -f "$SRC_SKILL_DIR/SKILL.md" ]]; then
  echo "ERROR: source skill file not found: $SRC_SKILL_DIR/SKILL.md" >&2
  exit 1
fi

if [[ ! -f "$SRC_QUERY_SCRIPT" ]]; then
  echo "ERROR: required query script not found: $SRC_QUERY_SCRIPT" >&2
  exit 1
fi

mkdir -p "$DEST_ROOT"

if [[ -d "$DEST_SKILL_DIR" ]]; then
  if [[ "$FORCE" -eq 1 ]]; then
    rm -rf "$DEST_SKILL_DIR"
  else
    echo "ERROR: destination already exists: $DEST_SKILL_DIR" >&2
    echo "Re-run with --force to overwrite." >&2
    exit 1
  fi
fi

mkdir -p "$DEST_SKILL_DIR/scripts"
cp "$SRC_SKILL_DIR/SKILL.md" "$DEST_SKILL_DIR/SKILL.md"
cp "$SRC_QUERY_SCRIPT" "$DEST_SKILL_DIR/scripts/query_health.py"
chmod +x "$DEST_SKILL_DIR/scripts/query_health.py"

echo "Installed skill '$SKILL_NAME' to: $DEST_SKILL_DIR"
echo "Restart Codex to pick up new skills."
