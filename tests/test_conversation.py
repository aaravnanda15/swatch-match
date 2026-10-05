"""Multi-turn stress tests for the WhatsApp chat bot (backend/conversation.py).

    python -m pytest tests -v

Every script runs twice: with Gemini (skipped when there is no key) and with
the AI switched off, i.e. the keyword fallback. See conftest.py for the setup.
"""

import re

from helpers import STOCK, Chat, is_red_saree

from backend import db


def test_1_kg_for_sarees_asks_to_confirm_pieces(mode):
    chat = Chat()
    first = chat.say("red saree?")
    assert is_red_saree(first) and first["pending_question"]["expects"] == "quantity"
    state = chat.say("67 kg")
    assert state["pending_question"]["expects"] == "confirm_quantity"
    assert state["pending_question"]["value"] == 67
    assert "67" in state["last_reply"] and "piece" in state["last_reply"].lower()
    if mode == "keywords":
        assert "sold by the piece, not by kg" in state["last_reply"]
    assert is_red_saree(state) and state["shortlist"] == first["shortlist"]


def test_2_plain_number_is_the_quantity_checked_against_stock(mode):
    chat = Chat()
    chat.say("red saree?")
    state = chat.say("67")
    assert state["quantity"] == 67 and state["unit"] == "piece"
    row = STOCK[state["focus"]]
    available = int(row["quantity_available"])
    reply = state["last_reply"]  # the AI may word it its own way, but the facts must be there
    assert row["design_id"] in reply
    if available == 0:
        assert state["pending_question"]["expects"] == "take_available"
    elif available < 67:
        assert str(available) in reply and state["pending_question"]["value"] == available
    else:
        assert str(available) in reply and state["pending_question"]["expects"] == "confirm_order"


def test_3_swearing_with_a_number_is_not_an_answer(mode):
    chat = Chat()
    first = chat.say("red saree?")
    state = chat.say("67 shit")
    assert state["last_intent"] == "abusive_or_nonsense"
    assert state["quantity"] is None
    assert state["enquiry"] == first["enquiry"] and state["shortlist"] == first["shortlist"]
    assert state["pending_question"]["expects"] == "quantity"
    assert "How many pieces of the red saree" in state["last_reply"]
    assert state["last_priority"] == "low"  # handled by the bot, not pushed to the seller


def test_4_three_off_topic_messages_close_and_flag(mode):
    chat = Chat()
    first = chat.say("yo bro")["last_reply"]
    second = chat.say("yo bro!")["last_reply"]
    assert first and second and first != second  # polite, and not the same canned line twice
    state = chat.say("yo bro??")
    assert state["flagged"] is True
    assert "Message us whenever you're ready" in state["last_reply"]


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
        assert design_id in state["last_reply"] and row["quantity_available"] in state["last_reply"]
    assert len(state["summary"]) < 300  # the running summary stays short however long the chat gets


def test_9_time_wasters_never_reach_the_seller(mode):
    chat = Chat()
    first = chat.say("red saree?")
    db.set_status(first["enquiry_id"], "sent")  # staff already replied with the shortlist
    for text in ["ok", "😂😂", "click here to earn money fast http://spam.example", "hmm", "hmm"]:
        state = chat.say(text)
        assert state["last_priority"] == "filtered" and state["last_reply"] == ""
        assert db.get_enquiry(first["enquiry_id"])["status"] == "sent", f"{text!r} was pushed to the seller"
    assert state["filtered_count"] >= 5 and is_red_saree(state)
    state = chat.say("20")
    assert state["last_priority"] == "needs_reply" and state["quantity"] == 20
    assert db.get_enquiry(first["enquiry_id"])["status"] == "new"  # a real answer does reach the seller


def test_10_things_the_shop_does_not_sell(mode):
    chat = Chat()
    first = chat.say("red saree?")
    state = chat.say("do you sell shoes?")
    assert "we only deal in sarees, dupattas and fabric" in state["last_reply"].lower()
    assert state["last_priority"] == "low"
    assert state["enquiry"] == first["enquiry"] and state["shortlist"] == first["shortlist"]
    chat.say("67 kg")  # now waiting for a yes/no: "do you sell shoes?" must not count as "yes"
    state = chat.say("do you sell shoes?")
    assert "only deal in sarees" in state["last_reply"] and state["quantity"] is None


def test_11_reply_to_all(mode, monkeypatch):
    from backend import whatsapp
    from backend.routes import whatsapp as routes

    monkeypatch.setattr(whatsapp, "enabled", lambda: True)
    a, b = Chat("wamid.CHAT"), Chat("wamid.CHAT")
    first = a.say("red saree?")
    a.say("lol")  # must not replace the unsent shortlist reply
    b.say("blue dupatta")
    b.say("10 pcs")

    ready = {r["enquiry_id"]: r for r in routes.inbox_ready()["items"]}
    mine = [ready[c.state()["enquiry_id"]] for c in (a, b)]
    assert mine[0]["picked"] and all(d["design_id"] in mine[0]["text"] for d in mine[0]["picked"])  # the shortlist
    assert mine[0]["said"][-1]["text"] == "lol"  # the seller sees what the buyer said since
    assert any(m["text"] == "10 pcs" for m in mine[1]["said"]) and mine[1]["picked"]
    # the unsent shortlist goes along with the answer
    assert all(d["design_id"] in mine[1]["text"] for d in mine[1]["picked"])

    items = [routes.SendRequest(enquiry_id=r["enquiry_id"], text=r["text"], language=r["language"],
                                picked=[d["design_id"] for d in r["picked"]]) for r in mine]
    result = routes.whatsapp_send_all(routes.SendAllRequest(items=items))
    assert result["sent"] == 2
    assert db.get_enquiry(first["enquiry_id"])["status"] == "sent"
    left = {r["enquiry_id"] for r in routes.inbox_ready()["items"]}
    assert not left & {r["enquiry_id"] for r in mine}
    again = routes.whatsapp_send_all(routes.SendAllRequest(items=items[:1]))
    assert again["sent"] == 0 and "already sent" in again["results"][0]["error"]  # never sent twice


def test_12_not_this_one_shows_something_else(mode):
    chat = Chat()
    first = chat.say("red saree?")
    state = chat.say("not this one, show me another")
    assert state["last_intent"] == "wants_other_designs"
    assert state["rejected"] == [first["focus"]]
    assert state["focus"] and state["focus"] != first["focus"] and state["focus"] in state["last_reply"]


def test_13_memory_keeps_the_occasion(mode):
    chat = Chat()
    chat.say("red saree for my daughter's wedding")
    chat.say("20")
    state = chat.say("how many in stock?")
    assert "Buying for a wedding" in state["memory"] and state["occasion"] == "wedding"
    assert is_red_saree(state)
