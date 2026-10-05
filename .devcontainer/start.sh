#!/usr/bin/env bash
# postStart: run the app in the background (log in /tmp/swatch.log)
cd "$(dirname "$0")/.."

# ssh sessions don't get Codespaces secrets; read the key from the file (base64)
SECRETS=/workspaces/.codespaces/shared/.env-secrets
if [ -z "$GEMINI_API_KEY" ] && [ -f "$SECRETS" ]; then
  value=$(grep '^GEMINI_API_KEY=' "$SECRETS" | cut -d= -f2-)
  [ -n "$value" ] && export GEMINI_API_KEY=$(echo "$value" | base64 -d)
fi

pkill -f "uvicorn backend.main:app" 2>/dev/null || true
# Codespaces kills what this script started when it exits, so detach and
# give it a moment before returning
setsid -f ./run.sh > /tmp/swatch.log 2>&1 < /dev/null
sleep 5
