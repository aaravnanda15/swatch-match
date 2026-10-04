#!/usr/bin/env bash
# One-command local run: ./run.sh
# Installs everything (first time only), builds the UI, starts the server
# on http://localhost:7860
set -e
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1  # show server log lines straight away

# 1. Python virtual environment + packages
if [ ! -d .venv ]; then
  echo "==> Creating Python virtual environment (.venv)"
  # Prefer Python 3.11 (the python3 that ships with macOS is too old)
  PY=$(command -v python3.11 || command -v python3)
  "$PY" -m venv .venv
fi
source .venv/bin/activate
if [ ! -f .venv/.installed ]; then
  echo "==> Installing Python packages (first run takes a few minutes)"
  python -m pip --version >/dev/null 2>&1 || python -m ensurepip
  python -m pip install --upgrade pip
  # Small CPU-only PyTorch build. If that index is unreachable, the normal
  # one gets installed by sentence-transformers instead (bigger download).
  python -m pip install torch --index-url https://download.pytorch.org/whl/cpu || true
  python -m pip install -r requirements.txt
  touch .venv/.installed
fi

# 2. .env file (empty key = fallback mode, still works)
if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> Created .env. Add your GEMINI_API_KEY there for full mode."
fi

# 3. Load the catalogue the first time (or after adding photos, run
#    `python -m backend.ingest` yourself)
if [ ! -f data/swatch.db ] || ! python -c "from backend import db; import sys; sys.exit(0 if db.list_designs() else 1)" 2>/dev/null; then
  echo "==> Loading catalogue (first time downloads the ~600 MB CLIP model)"
  python -m backend.ingest
fi

# 4. Frontend build
echo "==> Building the UI"
(cd frontend && { [ -d node_modules ] || npm install; } && npm run build)

# 5. Start the server
echo "==> Open http://localhost:7860"
exec uvicorn backend.main:app --host 0.0.0.0 --port 7860
