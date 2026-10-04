"""The agent: looks at what the buyer sent and calls the tools in a fixed,
explainable order. It never loops and works the same with or without the LLM.

    photo only      image_search -> describe_photo -> check_stock
    text only       parse_text -> attribute_filter -> text_search -> check_stock
    photo + text    image_search -> describe_photo -> parse_text -> attribute_filter
                    -> text_search -> narrow_to_lookalikes -> check_stock
                    ("this design but in blue": the photo finds the design,
                     the colour from the text re-ranks)
    vague text      parse_text -> ask_clarifying_question -> text_search -> check_stock
                    (nothing useful recognised: one question for the buyer, plus
                     a best-guess shortlist staff can ignore)

Every tool call is written to the trace so staff can see why they got
these results.
"""

import time

from backend import db
from backend.agent import scoring, tools
from backend.config import CONFIG

TOP_K = CONFIG["scoring"]["top_k"]
CANDIDATES = CONFIG["scoring"]["candidates"]
IMAGE_POOL = CONFIG["scoring"]["image_pool"]


class Trace:
    """A list of steps: which tool, why, what went in, what came out, how long."""

    def __init__(self):
        self.steps = []

    def add(self, tool, why, given, got, started):
        self.steps.append(
            {
                "step": len(self.steps) + 1,
                "tool": tool,
                "why": why,
                "input": given,
                "output": got,
                "ms": int((time.perf_counter() - started) * 1000),
            }
        )


def decide_mode(has_image, has_text):
    if has_image and has_text:
        return "image_and_text"
    if has_image:
        return "image_only"
    return "text_only"


def is_vague(query):
    """Text that gives us nothing to match on: no colour, pattern, fabric, work,
    border or budget. "saree" alone is still too broad for a useful shortlist."""
    useful = [a for a in query["attributes"] if a != "garment_type"]
    return not useful and not query["max_rate"]


def handle_enquiry(text, img):
    """text: the buyer's message ("" if none). img: a PIL image or None.
    Returns everything the Enquiry screen shows (see the return at the bottom)."""
    trace = Trace()
    text = (text or "").strip()
    mode = decide_mode(img is not None, bool(text))
    designs = {d["design_id"]: d for d in db.list_designs()}
    fallback_reasons = []
    clarifying_question = None

    image_scores, attr_scores, text_scores = {}, {}, {}
    photo = None  # tags + colour of the buyer's photo
    query = {"attributes": {}, "max_rate": None, "min_quantity": None, "language": "en", "source": None}

    # ---- 1. The photo ----
    if img is not None:
        t = time.perf_counter()
        vector = tools.encode_photo(img)
        image_scores = tools.image_search(vector)
        trace.add("image_search", "Buyer sent a photo: compare it with every catalogue photo",
                  "buyer's photo", f"closest: {', '.join(tools.top_ids(image_scores, 3))}", t)

        t = time.perf_counter()
        photo = tools.describe_photo(img, vector)
        if photo["llm_failed"]:
            fallback_reasons.append("The AI could not describe the photo, so basic photo tags were used.")
        trace.add("describe_photo", "Note the photo's pattern, border and shade, to explain each match",
                  "buyer's photo", _describe_tags(photo["tags"], photo["source"]), t)

    # ---- 2. The text ----
    if text:
        t = time.perf_counter()
        query = tools.parse_text_to_attributes(text)
        if query["llm_failed"]:
            fallback_reasons.append("The AI could not be reached, so the message was read with the keyword list.")
        elif query["source"] == "keywords":
            fallback_reasons.append("No AI key is set, so the message was read with the keyword list.")
        trace.add("parse_text_to_attributes", "Buyer sent text: work out what they are asking for",
                  text, _describe_query(query), t)

        if img is None and is_vague(query):
            mode = "vague"
            t = time.perf_counter()
            clarify = tools.ask_clarifying_question(text, query)
            if clarify["llm_failed"]:
                fallback_reasons.append("The AI could not write the question, so a standard one was used.")
            by = "Gemini" if clarify["source"] == "gemini" else "template"
            trace.add("ask_clarifying_question", "Too little to match on: ask the buyer one question",
                      text, f"{clarify['question']} (by {by})", t)
            clarifying_question = clarify["question"]

        if query["attributes"]:
            t = time.perf_counter()
            attr_scores = tools.attribute_filter(query["attributes"], designs.values())
            full = sum(1 for score, _ in attr_scores.values() if score == 1)
            trace.add("attribute_filter", "Compare the requested details with each design's tags",
                      query["attributes"], f"{full} of {len(designs)} designs match every detail", t)

        t = time.perf_counter()
        phrase = tools.english_phrase(query["attributes"], text)
        text_scores = tools.text_search(phrase)
        trace.add("text_search", "Compare the request in words with every catalogue photo",
                  phrase, f"closest: {', '.join(tools.top_ids(text_scores, 3))}", t)

    # ---- 3. Photo + text: the photo picks the design, the words re-rank ----
    pool = list(designs)
    if mode == "image_and_text":
        t = time.perf_counter()
        pool = tools.top_ids(image_scores, IMAGE_POOL)
        trace.add("narrow_to_lookalikes", "Photo and text: the photo picks the design, the words re-rank",
                  f"{len(designs)} designs", f"{len(pool)} that look most like the photo", t)

    # ---- 4. One score per design ----
    weights = scoring.weights_for(mode, bool(image_scores), bool(attr_scores), bool(text_scores))
    scores = {}
    for design_id in pool:
        signals = {
            "image": image_scores.get(design_id, 0.0),
            "attributes": attr_scores.get(design_id, (0.0, []))[0],
            "text": text_scores.get(design_id, 0.0),
        }
        scores[design_id] = (scoring.combine(signals, weights), signals)

    # ---- 5. Stock and rate (only from stock.csv); drop anything over budget ----
    ranked = sorted(pool, key=lambda d: -scores[d][0])[:CANDIDATES]
    t = time.perf_counter()
    stock = tools.check_stock([designs[d] for d in ranked], query["max_rate"], query["min_quantity"])
    over_budget = [d for d in ranked if not stock[d]["within_budget"]]
    kept = [d for d in ranked if stock[d]["within_budget"]][:TOP_K]
    got = f"{sum(stock[d]['in_stock'] for d in ranked)} of {len(ranked)} in stock"
    if query["max_rate"]:
        got += f"; {len(over_budget)} over ₹{query['max_rate']:g} removed"
    trace.add("check_stock", "Read stock and rate from stock.csv for the best candidates",
              f"top {len(ranked)} designs", got, t)

    # ---- 6. Label and explain each result (computed, not generated) ----
    # Only quote "same pattern/border" when Gemini described the photo; basic
    # CLIP photo tags are too rough to state as fact
    quotable_photo_tags = None
    if photo is not None:
        quotable_photo_tags = photo["tags"] if photo["source"] == "gemini" else {}

    results = []
    for design_id in kept:
        d = designs[design_id]
        score, signals = scores[design_id]
        matched = attr_scores.get(design_id, (0.0, []))[1]
        shade = None
        if photo is not None:
            shade = scoring.shade_difference(photo["colour"], tools.design_colour(d["image_file"]))
        label = scoring.label_for(score)
        # "Very close" only when everything the buyer asked for matches
        if label == "very_close" and len(matched) < len(query["attributes"]):
            label = "similar"
        results.append(
            {
                "design_id": design_id,
                "name": d["name"],
                "image_file": d["image_file"],
                "tags": d["tags"],
                "score": round(score, 3),
                "signals": {k: round(v, 3) for k, v in signals.items()},
                "label": label,
                "label_text": scoring.LABELS[label],
                "reason": scoring.reason_for(signals, d["tags"], query["attributes"], quotable_photo_tags, shade),
                "shade_note": scoring.needs_shade_note(query["attributes"], matched, shade, photo is not None),
                "matched_attributes": matched,
                **stock[design_id],
            }
        )

    # Nothing good enough: say so plainly and offer the nearest as alternatives
    no_match = not results or results[0]["label"] == "none"
    if no_match:
        for r in results:
            r["label"] = "none"
            r["label_text"] = "Best guess" if mode == "vague" else "Nearest alternative"

    return {
        "mode": mode,
        "fallback_mode": bool(fallback_reasons),
        "fallback_reason": " ".join(fallback_reasons) or None,
        "query": {k: query.get(k) for k in ("attributes", "max_rate", "min_quantity", "language")},
        "photo_tags": photo["tags"] if photo else None,
        "weights": {k: round(v, 2) for k, v in weights.items()},
        "no_match": no_match,
        "clarifying_question": clarifying_question,
        "over_budget_removed": len(over_budget),
        "results": results,
        "trace": trace.steps,
    }


def _describe_tags(tags, source):
    shown = [v for v in (tags.get("main_colour"), tags.get("pattern"), tags.get("garment_type")) if v]
    by = "Gemini" if source == "gemini" else "CLIP (basic)"
    return f"{' '.join(shown)} (described by {by})"


def _describe_query(query):
    parts = [f"{k.replace('_', ' ')}: {v}" for k, v in query["attributes"].items()]
    if query["max_rate"]:
        parts.append(f"budget up to ₹{query['max_rate']:g}")
    if query["min_quantity"]:
        parts.append(f"{query['min_quantity']:g} pieces")
    text = ", ".join(parts) or "nothing recognised"
    return f"{text} (read by {'Gemini' if query['source'] == 'gemini' else 'keyword list'})"
