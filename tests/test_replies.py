"""Replies the AI writes: the checks they must pass, and what happens when they fail.

    python -m pytest tests/test_replies.py -v
"""

import json
import re
import string

import pytest
from helpers import Chat, FakeLLM

from backend import conversation, db, llm
from backend.agent import templates
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


def test_notes_from_the_ai_are_remembered_and_used_later(fake):
    note = "Daughter's wedding in December"
    ai = fake(lambda c: {"reply": "Congratulations! " + c["template"], "needs_staff": False, "new_memory": [note]},
              lambda c: c["template"])
    chat = Chat()
    chat.say("red saree for my daughter's wedding in december")
    chat.say("20")
    assert note in chat.state()["memory"] and note in ai.calls[-1][0]["memory"]


# ---------- the templates, used when the AI is off or its reply fails a check ----------

STRAY = re.compile(r"\{|\}| {2}| [,.!?:।]|^[,.]|ji [,.]|for the [?.!]")


def test_every_template_fills_cleanly_with_or_without_a_name():
    values = dict(item="red saree", plural="Sarees", kind="sarees", unit="piece", units="pieces", units_n="pieces",
                  buyer_unit="kg", n=5, available=8, rate="₹1,450", name="Gold Kanchi Silk Saree", design="D003",
                  fabric="silk")
    for lang, keys in templates.TURN.items():
        for key in keys:
            for v in range(templates.variant_count(lang, key)):
                for extra in ({}, {"buyer": "Ramesh ji", "occasion": templates.occasion_words(lang, "wedding")}):
                    text = templates.turn_text(lang, key, v, **values, **extra)
                    assert not STRAY.search(text), f"{lang} {key} {v}: {text!r}"
                    raw = keys[key] if isinstance(keys[key], str) else keys[key][v]
                    if extra and "{buyer}" in raw:
                        assert "Ramesh ji" in text
    fields = {f for keys in templates.TURN.values() for k in keys.values()
              for t in ([k] if isinstance(k, str) else k) for _, f, _, _ in string.Formatter().parse(t) if f}
    assert fields <= set(values) | {"buyer", "occasion"}


def test_template_replies_use_the_buyer_name_and_item():
    with llm.offline():
        chat = Chat(name="Ramesh Textiles")
        first = chat.say("laal saree chahiye shaadi ke liye")
        assert "Ramesh ji" in first["last_reply"] and "shaadi ke liye" in first["last_reply"]
        assert "laal saree" in chat.say("lol")["last_reply"]  # the question names the item


def test_the_same_action_twice_is_worded_differently():
    with llm.offline():
        chat = Chat()
        chat.say("red saree?")
        first = chat.say("how many in stock?")["last_reply"]
        second = chat.say("what is the stock now?")["last_reply"]
    assert first.splitlines()[0] != second.splitlines()[0]  # "Here's the stock right now:" vs "Stock as of now:"
    assert first.splitlines()[-1] != second.splitlines()[-1]  # and the question after it


def test_a_formal_buyer_gets_no_emoji():
    with llm.offline():
        state = Chat(name="Buyer").say("Dear sir, kindly share red saree rates")
    assert state["tone"] == "formal" and "🙏" not in state["last_reply"]
    assert state["last_reply"].startswith("Namaste. ")


def test_a_returning_buyer_is_welcomed_with_their_last_design():
    with llm.offline():
        chat = Chat(name="Ramesh Textiles")
        chat.say("red saree?")
        chat.say("5")
        done = chat.say("yes")  # order confirmed
        assert done["stage"] == "done"
        state = chat.say("hi")
        assert done["focus"] in state["last_reply"] and "Ramesh ji" in state["last_reply"]
        with db.connect() as conn:  # a new chat, months later
            conn.execute("DELETE FROM conversations WHERE phone = ?", (chat.phone,))
        state = chat.say("blue dupatta")
        assert db.last_design(chat.phone) and "Last time" in state["last_reply"]


def test_back_in_stock_drafts_a_message_for_staff():
    with llm.offline():
        chat = Chat(name="Anita")
        first = chat.say("red saree?")
        waiting = first["waiting_for"]
        assert waiting, "the best red saree should be out of stock in the sample catalogue"
        design_id = waiting[0]
        db.set_status(first["enquiry_id"], "sent")
        db.update_stock(design_id, 6, db.get_design(design_id)["rate"])
        try:
            assert conversation.back_in_stock(design_id) >= 1  # every buyer who wanted it
        finally:
            db.update_stock(design_id, 0, db.get_design(design_id)["rate"])
        state = chat.state()
        assert state["outbox"]["intent"] == "back_in_stock" and design_id in state["outbox"]["text"]
        assert "6" in state["outbox"]["text"] and state["pending_question"]["expects"] == "quantity"
        assert db.get_enquiry(first["enquiry_id"])["status"] == "new" and not state["waiting_for"]
