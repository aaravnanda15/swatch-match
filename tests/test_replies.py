"""Replies the AI writes: the checks they must pass, and what happens when they fail.

    python -m pytest tests/test_replies.py -v
"""

from backend.agent.reply_guard import validate_reply

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
