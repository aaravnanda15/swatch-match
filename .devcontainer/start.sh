#!/usr/bin/env bash
# Runs every time the codespace starts: start the app in the background.
# Log: /tmp/swatch.log
cd "$(dirname "$0")/.."

# Codespaces secrets reach the lifecycle commands, but not ssh sessions; read
# the Gemini key from the secrets file if it is missing (values are base64)
SECRETS=/workspaces/.codespaces/shared/.env-secrets
if [ -z "$GEMINI_API_KEY" ] && [ -f "$SECRETS" ]; then
  value=$(grep '^GEMINI_API_KEY=' "$SECRETS" | cut -d= -f2-)
  [ -n "$value" ] && export GEMINI_API_KEY=$(echo "$value" | base64 -d)
fi

pkill -f "uvicorn backend.main:app" 2>/dev/null || true
# Own session, so it keeps running after this script ends. Codespaces cleans
# up right when the script exits, so give the app a moment to detach first.
setsid -f ./run.sh > /tmp/swatch.log 2>&1 < /dev/null
sleep 5
