"""Insights: how many sent replies the AI wrote, and how often staff edited them."""

from helpers import Chat

from backend import insights, llm, whatsapp
from backend.routes import whatsapp as routes


def test_insights_count_ai_and_template_replies(monkeypatch):
    monkeypatch.setattr(whatsapp, "enabled", lambda: True)
    before = insights.compute()["replies"]
    with llm.offline():
        a, b = Chat("wamid.CHAT"), Chat("wamid.CHAT")
        a.say("red saree?")
        b.say("blue dupatta")
    for chat, source, edited in ((a, "composed", False), (b, "template", True)):
        out = chat.state()["outbox"]
        routes.whatsapp_send(routes.SendRequest(enquiry_id=out["enquiry_id"], text=out["text"], picked=out["picked"],
                                                language=out["language"], draft_source=source, edited=edited))
    after = insights.compute()["replies"]
    assert after["composed"] == before["composed"] + 1 and after["template"] == before["template"] + 1
    assert after["edited"] == before["edited"] + 1 and after["checked"] == before["checked"] + 2
    assert after["template_share"] == round(after["template"] / (after["composed"] + after["template"]), 3)
    assert after["warn"] == (after["template_share"] > 0.10)
