#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$REPO_ROOT/dist"
STAGE_DIR="$OUT_DIR/openclaw-skill"

VERSION=""
CLEAN=0

usage() {
  cat <<USAGE
Package this repository's OpenClaw skill for publishing.

Usage:
  bash scripts/publish_openclaw_skill.sh [--version <tag>] [--out-dir <path>] [--clean]

Options:
  --version <tag>   Optional version label embedded in archive name (example: v1.1.0)
  --out-dir <path>  Output directory for staged files and zip (default: ./dist)
  --clean           Remove previous staged artifacts before packaging
  -h, --help        Show this help message
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      [[ $# -ge 2 ]] || { echo "ERROR: --version requires a value" >&2; exit 2; }
      VERSION="$2"
      shift 2
      ;;
    --out-dir)
      [[ $# -ge 2 ]] || { echo "ERROR: --out-dir requires a value" >&2; exit 2; }
      OUT_DIR="$2"
      STAGE_DIR="$OUT_DIR/openclaw-skill"
      shift 2
      ;;
    --clean)
      CLEAN=1
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

if [[ "$CLEAN" -eq 1 ]]; then
  rm -rf "$STAGE_DIR"
fi

mkdir -p "$STAGE_DIR/scripts"

cp "$REPO_ROOT/openclaw-skill/SKILL.md" "$STAGE_DIR/SKILL.md"
cp "$REPO_ROOT/openclaw-skill/WHOOP_SKILL.md" "$STAGE_DIR/WHOOP_SKILL.md"
cp "$REPO_ROOT/scripts/query_health.py" "$STAGE_DIR/scripts/query_health.py"
cp "$REPO_ROOT/scripts/query_live_hr.py" "$STAGE_DIR/scripts/query_live_hr.py"
cp "$REPO_ROOT/scripts/query_whoop.py" "$STAGE_DIR/scripts/query_whoop.py"

ARCHIVE_NAME="apple-health-skills-openclaw"
if [[ -n "$VERSION" ]]; then
  ARCHIVE_NAME+="-$VERSION"
fi
ARCHIVE_PATH="$OUT_DIR/$ARCHIVE_NAME.zip"

(
  cd "$OUT_DIR"
  rm -f "$ARCHIVE_PATH"
  zip -rq "$ARCHIVE_PATH" "openclaw-skill"
)

echo "Packaged OpenClaw skill: $ARCHIVE_PATH"
echo "Included files:"
echo "  - openclaw-skill/SKILL.md"
echo "  - openclaw-skill/WHOOP_SKILL.md"
echo "  - openclaw-skill/scripts/query_health.py"
echo "  - openclaw-skill/scripts/query_live_hr.py"
echo "  - openclaw-skill/scripts/query_whoop.py"
