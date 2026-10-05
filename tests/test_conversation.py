"""Multi-turn stress tests for the WhatsApp chat bot (backend/conversation.py).

    python -m pytest tests -v

Every script runs twice: with Gemini (skipped when there is no key) and with
the AI switched off, i.e. the keyword fallback. The tests use a copy of the
database, so the real one is never touched.
"""

import csv
import os
import random
import re
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
from backend import conversation, db, inbox, llm  # noqa: E402

db.init_db()
with db.connect() as conn:
    for table in ("conversations", "chat_messages", "wa_seen", "audit_log", "enquiries"):
        conn.execute(f"DELETE FROM {table}")

STOCK = {r["design_id"]: r for r in csv.DictReader(open(ROOT / "catalogue" / "stock.csv", encoding="utf-8"))}
STOCK_NUMBERS = {float(r["quantity_available"]) for r in STOCK.values()} | {float(r["rate"]) for r in STOCK.values()}
BANNED = {"bro", "yo", "bruh", "dude", "shit", "fuck", "fucking", "damn", "wtf", "lol", "bc", "mc"}
GEMINI_GAP = 4.2  # seconds between Gemini calls in tests, to stay under the free per-minute limit

provider = llm.get_llm()
if provider.available:
    _real = provider._generate_once
    _last = [0.0]

    def _paced(contents):
        wait = GEMINI_GAP - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        return _real(contents)

    provider._generate_once = _paced


@pytest.fixture(params=["gemini", "keywords"])
def mode(request):
    if request.param == "gemini" and not provider.available:
        pytest.skip("no GEMINI_API_KEY")
    if request.param == "keywords":
        with llm.offline():
            yield request.param
    else:
        yield request.param


class Chat:
    """One buyer, talking through the same path as a real WhatsApp message."""

    def __init__(self):
        self.phone = "9100" + str(random.randint(10**7, 10**8 - 1))
        self.said = []

    def say(self, text):
        self.said.append(text)
        inbox.handle_message({
            "id": f"wamid.TEST{time.time_ns()}", "phone": self.phone, "name": "Test Buyer",
            "timestamp": int(time.time()), "type": "text", "original_type": "text", "text": text, "media_id": None,
        })
        state = conversation.get_state(self.phone)
        check_reply(state["last_reply"], self.said)
        return state


def numbers_in(text):
    text = re.sub(r"\bD\d+\b", " ", text)          # design ids
    text = re.sub(r"(?m)^\s*\d+\.\s", " ", text)    # "1. " list numbering
    return {float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def check_reply(reply, buyer_messages):
    words = set(re.findall(r"[a-z]+", reply.lower()))
    assert not words & BANNED, f"slang or swearing in reply: {reply!r}"
    buyer_numbers = set().union(*(numbers_in(m) for m in buyer_messages))
    unknown = numbers_in(reply) - STOCK_NUMBERS - buyer_numbers
    assert not unknown, f"number not from stock.csv or the buyer: {unknown} in {reply!r}"


def is_red_saree(state):
    return state["enquiry"].get("main_colour") == "red" and state["enquiry"].get("garment_type") == "saree"


def test_1_kg_for_sarees_asks_to_confirm_pieces(mode):
    chat = Chat()
    first = chat.say("red saree?")
    assert is_red_saree(first) and first["pending_question"]["expects"] == "quantity"
    state = chat.say("67 kg")
    assert state["pending_question"]["expects"] == "confirm_quantity"
    assert state["pending_question"]["value"] == 67
    assert "67 pieces" in state["last_reply"] and "sold per piece" in state["last_reply"]
    assert is_red_saree(state) and state["shortlist"] == first["shortlist"]


def test_2_plain_number_is_the_quantity_checked_against_stock(mode):
    chat = Chat()
    chat.say("red saree?")
    state = chat.say("67")
    assert state["quantity"] == 67 and state["unit"] == "piece"
    row = STOCK[state["focus"]]
    available = int(row["quantity_available"])
    if available == 0:
        assert "out of stock" in state["last_reply"]
    elif available < 67:
        assert f"We have {available} pieces of {row['design_id']} in stock" in state["last_reply"]
        assert state["pending_question"]["value"] == available
    else:
        assert f"{available} pieces" in state["last_reply"]


def test_3_swearing_with_a_number_is_not_an_answer(mode):
    chat = Chat()
    first = chat.say("red saree?")
    state = chat.say("67 shit")
    assert state["last_intent"] == "abusive_or_nonsense"
    assert state["quantity"] is None
    assert state["enquiry"] == first["enquiry"] and state["shortlist"] == first["shortlist"]
    assert state["pending_question"]["expects"] == "quantity"
    assert "How many pieces of the red saree" in state["last_reply"]


def test_4_three_off_topic_messages_close_and_flag(mode):
    chat = Chat()
    replies = [chat.say("yo bro")["last_reply"] for _ in range(2)]
    assert all(r.startswith("I can help with") for r in replies)
    state = chat.say("yo bro")
    assert state["flagged"] is True
    assert "Our team will get back to you" in state["last_reply"]


def test_5_changed_colour_gives_a_new_shortlist(mode):
    chat = Chat()
    first = chat.say("red saree?")
    state = chat.say("actually blue")
    assert state["enquiry"]["main_colour"] == "blue"
    assert state["enquiry"]["garment_type"] == "saree"
    assert state["shortlist"] != first["shortlist"]
    top = db.get_design(state["shortlist"][0])
    assert top["tags"]["main_colour"] == "blue"


def test_6_hinglish_stays_hinglish(mode):
    chat = Chat()
    first = chat.say("laal saree chahiye")
    assert first["language"] == "hinglish" and is_red_saree(first)
    state = chat.say("50 piece")
    assert state["quantity"] == 50
    reply = state["last_reply"]
    assert re.search(r"\b(hain|hai|kya|chahiye|mein|piece)\b", reply), reply
    assert "We have" not in reply and "Yes, we have" not in reply


def test_8_forty_turns_of_nonsense_then_a_real_question(mode):
    chat = Chat()
    chat.say("red saree?")
    nonsense = ["yo", "bro", "lol", "🙂🙂", "asdfgh", "hmm", "???", "😂", "ok bro", "wtf", "dude", "...",
                "qwerty", "bruh", "🔥🔥", "lmao", "sup", "!!!", "zzz", "hehe"]
    for i in range(40):
        state = chat.say(nonsense[i % len(nonsense)])
        assert is_red_saree(state), f"enquiry lost after nonsense turn {i + 1}"
    assert state["flagged"] is True
    state = chat.say("how many in stock?")
    assert state["last_intent"] == "question_about_shown_designs"
    assert is_red_saree(state)
    for design_id in state["shortlist"][:3]:
        row = STOCK[design_id]
        assert f"{design_id} {row['name']}: {row['quantity_available']}" in state["last_reply"]
    assert len(state["summary"]) < 300  # the running summary stays short however long the chat gets
