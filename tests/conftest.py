"""Test setup: a copy of the database (the real one is never touched), and
Gemini calls spaced out to stay under the free per-minute limit."""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_tmp = Path(tempfile.mkdtemp(prefix="swatch-test-"))
os.environ["SWATCH_DB"] = str(_tmp / "swatch.db")  # must be set before backend is imported
if (ROOT / "data" / "swatch.db").exists():
    shutil.copy(ROOT / "data" / "swatch.db", _tmp / "swatch.db")
else:  # fresh clone: build the test database from the catalogue
    subprocess.run([sys.executable, "-m", "backend.ingest"], cwd=ROOT, check=True)

sys.path.insert(0, str(ROOT))
from backend import db, llm  # noqa: E402

db.init_db()
with db.connect() as conn:
    for table in ("conversations", "chat_messages", "wa_seen", "audit_log", "enquiries"):
        conn.execute(f"DELETE FROM {table}")

GEMINI_GAP = 4.2  # seconds between Gemini calls in tests

provider = llm.get_llm()
if provider.available:
    _real = provider._generate_once
    _last = [0.0]

    def _paced(*args, **kwargs):
        wait = GEMINI_GAP - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        return _real(*args, **kwargs)

    provider._generate_once = _paced


@pytest.fixture(params=["gemini", "keywords"])
def mode(request):
    """Run the test with Gemini (skipped when there is no key) and with the AI switched off."""
    if request.param == "gemini" and not provider.available:
        pytest.skip("no GEMINI_API_KEY")
    if request.param == "keywords":
        with llm.offline():
            yield request.param
    else:
        yield request.param
