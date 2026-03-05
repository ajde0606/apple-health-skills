#!/usr/bin/env bash
# stop.sh — Stop the Apple Health Bridge collector.
# Unloads the launchd agent (if installed) and terminates collector processes.
set -euo pipefail

LABEL="com.applehealthbridge.collector"
PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"

if launchctl list | grep -q "$LABEL"; then
    launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
    echo "Unloaded LaunchAgent: $LABEL"
elif [ -f "$PLIST_PATH" ]; then
    launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
    echo "Attempted unload of LaunchAgent plist: $PLIST_PATH"
else
    echo "LaunchAgent not loaded/installed: $LABEL"
fi

# Stop any collector process started manually (or still running after unload).
if pgrep -f "python -m mac.collector.main" >/dev/null 2>&1; then
    pkill -f "python -m mac.collector.main" >/dev/null 2>&1 || true
    echo "Stopped collector process: python -m mac.collector.main"
else
    echo "No running collector process found."
fi
