#!/usr/bin/env bash
# Runs every time the codespace starts: start the app in the background.
# Log: /tmp/swatch.log
cd "$(dirname "$0")/.."
pkill -f "uvicorn backend.main:app" 2>/dev/null || true
setsid nohup ./run.sh > /tmp/swatch.log 2>&1 < /dev/null &
