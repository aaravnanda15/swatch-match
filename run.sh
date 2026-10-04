#!/usr/bin/env bash
# One-command local run: ./run.sh
# Installs everything (first time only), builds the UI, starts the server
# on http://localhost:7860
set -e
cd "$(dirname "$0")"

# 1. Python virtual environment + packages
if [ ! -d .venv ]; then
  echo "==> Creating Python virtual environment (.venv)"
  python3 -m venv .venv
fi
source .venv/bin/activate
if [ ! -f .venv/.installed ]; then
  echo "==> Installing Python packages (first run takes a few minutes)"
  pip install --upgrade pip
  # Small CPU-only PyTorch build. If that index is unreachable, the normal
  # one gets installed by sentence-transformers instead (bigger download).
  pip install torch --index-url https://download.pytorch.org/whl/cpu || true
  pip install -r requirements.txt
  touch .venv/.installed
fi

# 2. .env file (empty key = fallback mode, still works)
if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> Created .env. Add your GEMINI_API_KEY there for full mode."
fi

# 3. Frontend build
echo "==> Building the UI"
(cd frontend && { [ -d node_modules ] || npm install; } && npm run build)

# 4. Start the server
echo "==> Open http://localhost:7860"
exec uvicorn backend.main:app --host 0.0.0.0 --port 7860
