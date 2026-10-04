#!/usr/bin/env bash
# Runs once when the codespace is created: everything run.sh does except
# starting the server (start.sh does that).
set -e
cd "$(dirname "$0")/.."
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu || true
python -m pip install -r requirements.txt
python -c "import hashlib; print(hashlib.sha1(open('requirements.txt', 'rb').read()).hexdigest())" > .venv/.installed
[ -f .env ] || cp .env.example .env
python -m backend.ingest
(cd frontend && npm install --no-audit --no-fund --loglevel=error && npm run build)
