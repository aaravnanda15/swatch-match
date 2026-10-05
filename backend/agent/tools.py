"""The agent's tools."""

import numpy as np

from backend import db, embeddings, llm, tagging, vector_index
from backend.agent import lexicon, scoring, templates
from backend.config import ATTRIBUTES, CATALOGUE_DIR
from backend.images import colour_histogram, colour_profile, load_image_file

LANGUAGES = ("en", "hi", "gu", "hinglish")


def encode_photo(img):
    """The buyer's photo as a CLIP vector (used by image_search and describe_photo)."""
    return embeddings.encode_images([img])[0]


def image_search(query_vector, img=None):
    """Compare the buyer's photo with the catalogue photos: CLIP for the look, plus
    how close the colours are (CLIP alone mixes up designs of different colours)."""
    sims = vector_index.search(query_vector)
    if img is not None:
        wanted = colour_histogram(img)
        weight = scoring.SCORING["colour_weight"]
        designs = {d["design_id"]: d["image_file"] for d in db.list_designs()}
        sims = {d: s + weight * float(np.minimum(wanted, design_histogram(designs[d])).sum()) if d in designs else s
                for d, s in sims.items()}
    return {d: scoring.stretch(s, scoring.SCORING["image_range"]) for d, s in sims.items()}


_design_histograms = {}


def design_histogram(image_file):
    path = CATALOGUE_DIR / image_file
    key = (image_file, path.stat().st_mtime)
    if key not in _design_histograms:
        _design_histograms[key] = colour_histogram(load_image_file(path))
    return _design_histograms[key]


def parse_text_to_attributes(text):
    """Read the buyer's message."""
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
    attributes = {}
    raw = answer.get("attributes")
    for attr, value in (raw if isinstance(raw, dict) else {}).items():
        value = str(value).strip().lower()
        if attr in ATTRIBUTES and value in ATTRIBUTES[attr]:
            attributes[attr] = value
    result["attributes"] = attributes
    result["max_rate"] = lexicon._sensible_budget(_positive_number(answer.get("max_rate")))
    result["min_quantity"] = _positive_number(answer.get("min_quantity"))
    if answer.get("language") in LANGUAGES:
        result["language"] = answer["language"]
    result["source"] = "gemini"
    return result


def describe_photo(img, query_vector):
    """Tags (Gemini, or CLIP if Gemini is off/fails) and a colour summary of the buyer's photo, so reasons can say "same pattern and border, shade darker"."""
    tags, source = tagging.tag_image(img, query_vector)
    provider = llm.get_llm()
    return {
        "tags": tags,
        "colour": colour_profile(img),
        "source": source,
        "llm_failed": provider.available and source != "gemini",
        "ai_available": provider.available,
    }


_design_colours = {}


def design_colour(image_file):
    path = CATALOGUE_DIR / image_file
    key = (image_file, path.stat().st_mtime)
    if key not in _design_colours:
        _design_colours[key] = colour_profile(load_image_file(path))
    return _design_colours[key]


def ask_clarifying_question(text, query):
    """One question back to the buyer when the enquiry is too vague."""
    language = query.get("language", "en")
    provider = llm.get_llm()
    if provider.available:
        known = ", ".join(query["attributes"].values())
        answer = provider.clarify(text, known, language)
        question = answer.get("question") if isinstance(answer, dict) else None
        # Accept only a short single question with no numbers (no prices or stock)
        if isinstance(question, str) and 5 < len(question) <= 300 and not any(ch.isdigit() for ch in question):
            return {"question": question.strip(), "source": "gemini", "llm_failed": False}
    return {
        "question": templates.clarifying_question(language, query["attributes"]),
        "source": "template",
        "llm_failed": provider.available,
    }


def draft_reply(design_ids, language, no_match=False, min_quantity=None):
    """Reply text for the designs staff picked."""
    designs = [db.get_design(d) for d in design_ids]
    designs = [d for d in designs if d is not None]
    return templates.draft_reply(language, designs, no_match=no_match, min_quantity=min_quantity)


def _positive_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def english_phrase(attributes, fallback_text):
    """CLIP only understands English, so describe the request in plain English ("a photo of a red bandhani saree")."""
    if not attributes:
        return fallback_text
    words = [attributes.get(a) for a in ("main_colour", "fabric", "pattern", "work_type")]
    words = [w for w in words if w and w not in ("none", "other", "unknown", "plain")]
    garment = attributes.get("garment_type", "fabric")
    if garment == "other":
        garment = "fabric"
    return "a photo of a " + " ".join(words + [garment])


def text_search(phrase):
    """Compare a text description with the catalogue photos (CLIP)."""
    sims = vector_index.search(embeddings.encode_texts([phrase])[0])
    return {d: scoring.stretch(s, scoring.SCORING["text_range"]) for d, s in sims.items()}


def attribute_filter(wanted, designs):
    """Score each design's tags against the wanted attributes."""
    return {d["design_id"]: scoring.attribute_match(wanted, d["tags"]) for d in designs}


def check_stock(designs, max_rate=None, min_quantity=None):
    """Stock and rate straight from the stock table (loaded only from stock.csv)."""
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
    ids = list(scores)
    values = np.array([scores[i] for i in ids])
    return [ids[i] for i in np.argsort(-values)[:n]]
