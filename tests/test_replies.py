"""Replies the AI writes: the checks they must pass, and what happens when they fail.

    python -m pytest tests/test_replies.py -v
"""

import json

import pytest
from helpers import Chat, FakeLLM

from backend import db, llm
from backend.agent.reply_guard import validate_reply
from backend.config import CONFIG

FACTS = {"designs": [{"design_id": "D003", "name": "Gold Kanchi Silk Saree", "rate": 1450.0, "unit": "piece",
                      "stock": 8, "fabric": "silk", "colour": "gold", "pattern": "plain", "work": "zari weave"}]}


def test_guard_rejects_an_invented_rate():
    problems = validate_reply("Gold Kanchi Silk Saree (D003) is ₹1,800 a piece, 8 in stock.", FACTS, "en")
    assert problems == ["you wrote 1800, but in FACTS the rate of D003 is 1450"]


def test_guard_checks_hindi_and_gujarati_digits():
    assert validate_reply("D003 के ८ पीस स्टॉक में हैं, ₹१,४५० प्रति पीस।", FACTS, "hi") == []
    assert "you wrote 9" in validate_reply("D003 के ९ पीस स्टॉक में हैं।", FACTS, "hi")[0]


def test_guard_rejects_the_wrong_script():
    english = "Gold Kanchi Silk Saree (D003) is in stock, 8 pieces at ₹1,450 each."
    assert validate_reply(english, FACTS, "gu") == ["write it in Gujarati in Gujarati script"]
    gujarati = "Gold Kanchi Silk Saree (D003) સ્ટોકમાં છે: 8 પીસ, ₹1,450 પ્રતિ પીસ."
    assert validate_reply(gujarati, FACTS, "gu") == []  # the English design name doesn't count


def test_guard_keeps_what_the_shop_decided():
    template = "Yes, Gold Kanchi Silk Saree (D003) is in stock: 8 pieces at ₹1,450 a piece."
    problems = validate_reply("Yes, the gold Kanchi silk is available at ₹1,450!", FACTS, "en", template=template)
    assert "you left out D003" in problems and "you left out 8" in problems


def test_guard_style_rules():
    assert validate_reply("Sure bro, D003 has 8 left.", FACTS, "en") == ["it has slang or rude words"]
    assert validate_reply("D003 — 8 left.", FACTS, "en") == ["it has an em dash, use a comma or a full stop"]
    assert "keep it under 500" in validate_reply("D003 has 8 left. " * 40, FACTS, "en")[0]
    assert validate_reply("20 pieces of D003, noted.", FACTS, "en", buyer_text="20 pcs") == []


@pytest.fixture
def fake(monkeypatch):
    """Use as fake(reply, reply, ...): the AI's answers in order (each a function of the composer's input)."""
    def use(*replies):
        provider = FakeLLM(*replies)
        monkeypatch.setattr(llm, "get_llm", lambda: provider)
        return provider
    return use


def added(text):
    return lambda c: f"{c['template']}\n{text}"


def test_an_invented_number_is_never_used(fake):
    ai = fake(added("Special rate today: ₹999!"), added("Only ₹999 for you!"))
    state = Chat().say("red saree?")
    assert state["reply_source"] == "template" and "999" not in state["last_reply"]
    assert ai.calls[1][1][0].startswith("you wrote 999, but in FACTS the")  # the retry was told why


def test_a_reply_that_is_fixed_on_the_retry_is_used(fake):
    ai = fake(added("Special rate today: ₹999!"), lambda c: "Lovely choice for the season! " + c["template"])
    state = Chat().say("red saree?")
    assert state["reply_source"] == "composed" and len(ai.calls) == 2
    assert state["last_reply"].startswith("Lovely choice for the season!")
    step = db.get_enquiry(state["enquiry_id"])["answer"]["trace"][-1]
    assert step["tool"] == "compose_reply" and step["output"].startswith("written by AI")
    assert state["outbox"]["source"] == "composed"


def in_english(c):
    designs = json.loads(c["facts"])["designs"]
    return "Here you go: " + ", ".join(f"{d['name']} ({d['design_id']}) ₹{d['rate']:,.0f}, {d['stock']} in stock"
                                       for d in designs)


def test_a_reply_in_the_wrong_script_is_rejected(fake):
    ai = fake(in_english, in_english)
    state = Chat().say("લાલ સાડી જોઈએ છે")
    assert state["language"] == "gu" and ai.calls[1][1] == ["write it in Gujarati in Gujarati script"]
    assert state["reply_source"] == "template" and "સ્ટોકમાં" in state["last_reply"]


def test_no_ai_reply_when_switched_off(fake, monkeypatch):
    monkeypatch.setitem(CONFIG["llm"], "compose_replies", False)
    ai = fake(lambda c: "never used")
    state = Chat().say("red saree?")
    assert state["reply_source"] == "template" and not ai.calls
