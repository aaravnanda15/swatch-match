"""Checks a reply the AI wrote before staff see it.

Stock, rates and design IDs must come from the database, so any number or
design ID that isn't in FACTS (or in the buyer's own message) rejects the reply.
"""

import json
import re

from backend.agent import lexicon

MAX_CHARS = 500
DESIGN_ID = re.compile(r"\bD\d+\b")
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
WORD = re.compile(r"[a-z]+|[ऀ-ॿ]+|[઀-૿]+")
LANGUAGE_NAMES = {"en": "English", "hinglish": "Hinglish (Hindi in English letters)",
                  "hi": "Hindi in Devanagari script", "gu": "Gujarati in Gujarati script"}


def numbers(text):
    text = lexicon.translate_digits(text)
    text = DESIGN_ID.sub(" ", text)
    text = re.sub(r"(?m)^\s*\d+[.)]\s", " ", text)  # "1. " list numbering
    return {float(n.replace(",", "")) for n in NUMBER.findall(text)}


def validate_reply(reply, facts, language, template="", buyer_text=""):
    """What is wrong with the reply, as notes the AI can fix. [] means it is fine."""
    if not reply.strip():
        return ["the reply is empty"]
    problems = []

    allowed = numbers(json.dumps(facts, ensure_ascii=False)) | numbers(buyer_text)
    for n in sorted(numbers(reply) - allowed):
        problems.append(f"you wrote {n:g}, {_nearest(n, facts)}")

    ids = set(DESIGN_ID.findall(reply))
    known = {d["design_id"] for d in facts.get("designs", [])}
    problems += [f"{d} is not one of the designs in FACTS" for d in sorted(ids - known)]
    # the reply must still say what the shop decided
    problems += [f"you left out {d}" for d in sorted(set(DESIGN_ID.findall(template)) - ids)]
    problems += [f"you left out {n:g}" for n in sorted(numbers(template) - numbers(reply))]

    if not _script_ok(reply, facts, language):
        problems.append(f"write it in {LANGUAGE_NAMES.get(language, 'English')}")
    limit = max(MAX_CHARS, len(template) + 80)
    if len(reply) > limit:
        problems.append(f"it is {len(reply)} characters long, keep it under {limit}")
    if set(WORD.findall(reply.lower())) & (lexicon.SWEAR | lexicon.SLANG):
        problems.append("it has slang or rude words")
    if "—" in reply:
        problems.append("it has an em dash, use a comma or a full stop")
    if re.search(r"(?m)^#|\*\*", reply):
        problems.append("it has markdown, write plain WhatsApp text")
    return problems


def _nearest(n, facts):
    options = []
    for d in facts.get("designs", []):
        options.append((d["rate"], f"the rate of {d['design_id']} is {d['rate']:g}"))
        options.append((d["stock"], f"the stock of {d['design_id']} is {d['stock']:g}"))
    if not options:
        return "which is not in FACTS"
    _, text = min(options, key=lambda o: abs(o[0] - n))
    return f"but in FACTS {text}"


def _script_ok(reply, facts, language):
    # design names stay in English in every language, so leave them out of the count
    text = reply
    for d in facts.get("designs", []):
        text = text.replace(d["name"], " ").replace(d["design_id"], " ")
    latin = len(re.findall(r"[A-Za-z]", text))
    hindi = len(re.findall(r"[ऀ-ॿ]", text))
    gujarati = len(re.findall(r"[઀-૿]", text))
    total = latin + hindi + gujarati
    if not total:
        return True
    if language == "gu":
        return gujarati / total > 0.5
    if language == "hi":
        return hindi / total > 0.5
    return latin / total >= 0.8
