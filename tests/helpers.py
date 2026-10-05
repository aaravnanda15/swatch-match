import csv
import random
import re
import time

from conftest import ROOT

from backend import conversation, inbox
from backend.config import CONFIG

STOCK = {r["design_id"]: r for r in csv.DictReader(open(ROOT / "catalogue" / "stock.csv", encoding="utf-8"))}
STOCK_NUMBERS = {float(r["quantity_available"]) for r in STOCK.values()} | {float(r["rate"]) for r in STOCK.values()}
BANNED = {"bro", "yo", "bruh", "dude", "shit", "fuck", "fucking", "damn", "wtf", "lol", "bc", "mc"}


class Chat:
    """One buyer, talking through the same path as a real WhatsApp message."""

    def __init__(self, prefix="wamid.TEST", name="Test Buyer", phone=None):
        self.phone = phone or "9100" + str(random.randint(10**7, 10**8 - 1))
        self.name = name
        self.said = []
        self.prefix = prefix  # wamid.CHAT = a simulated buyer, so replies never go to Meta

    def say(self, text):
        self.said.append(text)
        inbox.handle_message({
            "id": f"{self.prefix}{time.time_ns()}", "phone": self.phone, "name": self.name,
            "timestamp": int(time.time()), "type": "text", "original_type": "text", "text": text, "media_id": None,
        })
        state = conversation.get_state(self.phone)
        check_reply(state["last_reply"], self.said)
        return state

    def state(self):
        return conversation.get_state(self.phone)


def numbers_in(text):
    text = re.sub(r"\bD\d+\b", " ", text)          # design ids
    text = re.sub(r"(?m)^\s*\d+\.\s", " ", text)    # "1. " list numbering
    return {float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def check_reply(reply, buyer_messages):
    """No slang, and every number is from stock.csv, the shop's terms or the buyer."""
    words = set(re.findall(r"[a-z]+", reply.lower()))
    assert not words & BANNED, f"slang or swearing in reply: {reply!r}"
    buyer_numbers = set().union(*(numbers_in(m) for m in buyer_messages))
    unknown = numbers_in(reply) - STOCK_NUMBERS - SHOP_NUMBERS - buyer_numbers
    assert not unknown, f"number not from stock.csv or the buyer: {unknown} in {reply!r}"


SHOP_NUMBERS = set().union(*(numbers_in(t) for texts in CONFIG["shop"].values() for t in texts.values()))


def is_red_saree(state):
    return state["enquiry"].get("main_colour") == "red" and state["enquiry"].get("garment_type") == "saree"


class FakeLLM:
    """Stands in for Gemini. Each reply is a function of what the composer was given;
    the message reading falls back to keywords, so the tests are fast and repeatable."""

    name = "fake"
    available = True
    last_error = None

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []  # (context, problems) for every compose call

    def compose_reply(self, context, problems=()):
        self.calls.append((context, list(problems)))
        if not self.replies:
            return None
        answer = self.replies.pop(0)(context)
        return answer if isinstance(answer, dict) else {"reply": answer, "needs_staff": False, "new_memory": []}

    def classify_turn(self, *args):
        return None

    def parse_text(self, text):
        return None

    def clarify(self, *args):
        return None

    def tag_image(self, *args):
        return None
