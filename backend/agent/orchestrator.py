"""The agent: looks at what the buyer sent and calls the tools in a fixed,
explainable order. It never loops and works the same with or without the LLM.

    photo only      image_search -> check_stock
    text only       parse_text -> attribute_filter -> text_search -> check_stock
    photo + text    image_search -> parse_text -> attribute_filter -> text_search
                    -> narrow_to_lookalikes -> check_stock
                    ("this design but in blue": the photo finds the design,
                     the colour from the text re-ranks)
    vague text      text with nothing recognisable: same as text only for now;
                    step 5 adds a clarifying question

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


def handle_enquiry(text, img):
    """text: the buyer's message ("" if none). img: a PIL image or None.
    Returns {"mode", "fallback_mode", "fallback_reason", "query", "results", "trace"}."""
    trace = Trace()
    text = (text or "").strip()
    mode = decide_mode(img is not None, bool(text))
    designs = {d["design_id"]: d for d in db.list_designs()}
    fallback_reason = None

    image_scores, attr_scores, text_scores = {}, {}, {}
    query = {"attributes": {}, "max_rate": None, "min_quantity": None, "language": "en"}

    if img is not None:
        t = time.perf_counter()
        image_scores = tools.image_search(img)
        best = tools.top_ids(image_scores, 3)
        trace.add("image_search", "Buyer sent a photo: compare it with every catalogue photo",
                  "buyer's photo", f"closest: {', '.join(best)}", t)

    if text:
        t = time.perf_counter()
        query = tools.parse_text_to_attributes(text)
        if query["llm_failed"]:
            fallback_reason = "The AI could not be reached, so the message was read with the keyword list."
        elif query["source"] == "keywords":
            fallback_reason = "No AI key is set, so the message was read with the keyword list."
        trace.add("parse_text_to_attributes", "Buyer sent text: work out what they are asking for",
                  text, _describe_query(query), t)

        if not query["attributes"] and not query["max_rate"] and img is None:
            mode = "vague"

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

    # Photo + text: keep only designs that look like the photo, so the words
    # re-rank similar designs instead of pulling in unrelated ones
    pool = list(designs)
    if mode == "image_and_text":
        t = time.perf_counter()
        pool = tools.top_ids(image_scores, IMAGE_POOL)
        trace.add("narrow_to_lookalikes", "Photo and text: the photo picks the design, the words re-rank",
                  f"{len(designs)} designs", f"{len(pool)} that look most like the photo", t)

    # Combine the signals into one score per design
    weights = scoring.weights_for(mode, bool(image_scores), bool(attr_scores), bool(text_scores))
    scores = {}
    for design_id in pool:
        signals = {
            "image": image_scores.get(design_id, 0.0),
            "attributes": attr_scores.get(design_id, (0.0, []))[0],
            "text": text_scores.get(design_id, 0.0),
        }
        scores[design_id] = (scoring.combine(signals, weights), signals)

    # Stock and rate for the best candidates; drop anything over budget
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

    results = []
    for design_id in kept:
        d = designs[design_id]
        score, signals = scores[design_id]
        results.append(
            {
                "design_id": design_id,
                "name": d["name"],
                "image_file": d["image_file"],
                "tags": d["tags"],
                "score": round(score, 3),
                "signals": {k: round(v, 3) for k, v in signals.items()},
                "matched_attributes": attr_scores.get(design_id, (0.0, []))[1],
                **stock[design_id],
            }
        )

    return {
        "mode": mode,
        "fallback_mode": fallback_reason is not None,
        "fallback_reason": fallback_reason,
        "query": {k: query.get(k) for k in ("attributes", "max_rate", "min_quantity", "language")},
        "weights": {k: round(v, 2) for k, v in weights.items()},
        "results": results,
        "trace": trace.steps,
    }


def _describe_query(query):
    parts = [f"{k.replace('_', ' ')}: {v}" for k, v in query["attributes"].items()]
    if query["max_rate"]:
        parts.append(f"budget up to ₹{query['max_rate']:g}")
    if query["min_quantity"]:
        parts.append(f"{query['min_quantity']:g} pieces")
    text = ", ".join(parts) or "nothing recognised"
    return f"{text} (read by {'Gemini' if query['source'] == 'gemini' else 'keyword list'})"
