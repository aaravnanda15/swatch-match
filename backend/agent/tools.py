"""The agent's tools. Each one does a single job and returns plain data.
The orchestrator decides which to call and logs every call to the trace.

Clarifying question and draft reply tools are added in steps 5 and 6.
"""

import numpy as np

from backend import db, embeddings, llm
from backend.agent import lexicon, scoring
from backend.config import ATTRIBUTES

LANGUAGES = ("en", "hi", "gu", "hinglish")


def image_search(img):
    """Compare the buyer's photo with every catalogue photo.
    Returns {design_id: similarity 0-1}."""
    ids, matrix = db.load_embeddings()
    if not ids:
        return {}
    query = embeddings.encode_images([img])[0]
    raw = matrix @ query
    return {d: scoring.stretch(float(s), scoring.SCORING["image_range"]) for d, s in zip(ids, raw)}


def parse_text_to_attributes(text):
    """Read the buyer's message. Gemini first; the keyword list fills anything
    Gemini missed, and does the whole job when Gemini is off or fails.

    Returns {"attributes", "max_rate", "min_quantity", "language", "source", "llm_failed"}."""
    result = lexicon.parse(text)
    result["source"] = "keywords"
    result["llm_failed"] = False

    provider = llm.get_llm()
    if not provider.available:
        return result
    answer = provider.parse_text(text)
    if not isinstance(answer, dict):
        result["llm_failed"] = True
        return result

    # Keep only values from the fixed vocabulary; never trust the LLM blindly
    for attr, value in (answer.get("attributes") or {}).items():
        value = str(value).strip().lower()
        if attr in ATTRIBUTES and value in ATTRIBUTES[attr]:
            result["attributes"][attr] = value
    for key in ("max_rate", "min_quantity"):
        number = _positive_number(answer.get(key))
        if number is not None:
            result[key] = number
    if answer.get("language") in LANGUAGES:
        result["language"] = answer["language"]
    result["source"] = "gemini"
    return result


def _positive_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def english_phrase(attributes, fallback_text):
    """CLIP only understands English, so describe the request in plain English
    ("a photo of a red bandhani saree"). Uses the buyer's own words if nothing
    was recognised."""
    if not attributes:
        return fallback_text
    words = [attributes.get(a) for a in ("main_colour", "fabric", "pattern", "work_type")]
    words = [w for w in words if w and w not in ("none", "other", "unknown", "plain")]
    garment = attributes.get("garment_type", "fabric")
    if garment == "other":
        garment = "fabric"
    return "a photo of a " + " ".join(words + [garment])


def text_search(phrase):
    """Compare a text description with every catalogue photo (CLIP).
    Returns {design_id: similarity 0-1}."""
    ids, matrix = db.load_embeddings()
    if not ids:
        return {}
    query = embeddings.encode_texts([phrase])[0]
    raw = matrix @ query
    return {d: scoring.stretch(float(s), scoring.SCORING["text_range"]) for d, s in zip(ids, raw)}


def attribute_filter(wanted, designs):
    """Score each design's tags against the wanted attributes.
    Returns {design_id: (score 0-1, [attributes that matched])}."""
    return {d["design_id"]: scoring.attribute_match(wanted, d["tags"]) for d in designs}


def check_stock(designs, max_rate=None, min_quantity=None):
    """Stock and rate straight from the stock table (loaded only from stock.csv).
    Returns {design_id: {quantity_available, rate, unit, in_stock, enough_stock, within_budget}}."""
    info = {}
    for d in designs:
        quantity = d["quantity_available"]
        info[d["design_id"]] = {
            "quantity_available": quantity,
            "rate": d["rate"],
            "unit": d["unit"],
            "in_stock": quantity > 0,
            "enough_stock": quantity >= (min_quantity or 1),
            "within_budget": max_rate is None or d["rate"] <= max_rate,
        }
    return info


def top_ids(scores, n):
    """The n design_ids with the highest score."""
    ids = list(scores)
    values = np.array([scores[i] for i in ids])
    return [ids[i] for i in np.argsort(-values)[:n]]
