#!/usr/bin/env bash
# One-command local run: ./run.sh
# Installs everything (first time only), builds the UI, starts the server
# on http://localhost:7860
set -e
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1  # show server log lines straight away

# 1. Python virtual environment + packages
if [ ! -d .venv ]; then
  # Python 3.10 or newer is needed (the python3 that ships with macOS is 3.9)
  PY=""
  for candidate in python3.11 python3.12 python3.13 python3.10 python3; do
    if command -v "$candidate" >/dev/null && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
      PY=$(command -v "$candidate"); break
    fi
  done
  if [ -z "$PY" ]; then
    echo "Swatch Match needs Python 3.10 or newer (3.11 recommended). See README, 'Run it on your computer'."
    exit 1
  fi
  echo "==> Creating Python virtual environment (.venv) with $("$PY" --version)"
  "$PY" -m venv .venv
fi
source .venv/bin/activate
# Install again whenever requirements.txt changes (its fingerprint is kept in .venv/.installed)
REQS=$(python -c "import hashlib; print(hashlib.sha1(open('requirements.txt', 'rb').read()).hexdigest())")
if [ "$(cat .venv/.installed 2>/dev/null)" != "$REQS" ]; then
  echo "==> Installing Python packages (first run takes a few minutes)"
  python -m pip --version >/dev/null 2>&1 || python -m ensurepip
  python -m pip install --upgrade pip
  # Small CPU-only PyTorch build. If that index is unreachable, the normal
  # one gets installed by sentence-transformers instead (bigger download).
  python -m pip install torch --index-url https://download.pytorch.org/whl/cpu || true
  python -m pip install -r requirements.txt
  echo "$REQS" > .venv/.installed
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
# npm install is quick when nothing changed, and picks up new packages after a git pull
(cd frontend && npm install --no-audit --no-fund --loglevel=error && npm run build)

# 5. Start the server
echo "==> Open http://localhost:7860"
exec uvicorn backend.main:app --host 0.0.0.0 --port 7860
