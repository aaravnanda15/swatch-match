"""The agent: looks at what the buyer sent and calls the tools in a fixed, explainable order."""

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
    """Text that gives us nothing to match on: no colour, pattern, fabric, work, border or budget."""
    useful = [a for a in query["attributes"] if a != "garment_type"]
    return not useful and not query["max_rate"]


class Run:
    """What one enquiry collects as it goes through the steps below."""

    def __init__(self, text, img):
        self.text = (text or "").strip()
        self.img = img
        self.trace = Trace()
        self.mode = decide_mode(img is not None, bool(self.text))
        self.designs = {d["design_id"]: d for d in db.list_designs()}
        self.fallback_reasons = []
        self.clarifying_question = None
        self.photo = None
        self.query = {"attributes": {}, "max_rate": None, "min_quantity": None, "language": "en", "source": None}
        self.image_scores, self.attr_scores, self.text_scores = {}, {}, {}


def handle_enquiry(text, img):
    """text: the buyer's message ("" if none)."""
    run = Run(text, img)
    if run.img is not None:
        read_photo(run)
    if run.text:
        read_text(run)
    pool = narrow_to_lookalikes(run)
    scores, weights = score_designs(run, pool)
    kept, stock, over_budget = check_stock_and_budget(run, pool, scores)
    results, no_match = label_results(run, kept, scores, stock)

    return {
        "mode": run.mode,
        "fallback_mode": bool(run.fallback_reasons),
        "fallback_reason": " ".join(run.fallback_reasons) or None,
        "query": {k: run.query.get(k) for k in ("attributes", "max_rate", "min_quantity", "language")},
        "photo_tags": run.photo["tags"] if run.photo else None,
        "weights": {k: round(v, 2) for k, v in weights.items()},
        "no_match": no_match,
        "clarifying_question": run.clarifying_question,
        "over_budget_removed": len(over_budget),
        "results": results,
        "trace": run.trace.steps,
    }


def read_photo(run):
    """Compare the buyer's photo with every catalogue photo, and describe it."""
    t = time.perf_counter()
    vector = tools.encode_photo(run.img)
    run.image_scores = tools.image_search(vector)
    run.trace.add("image_search", "Buyer sent a photo: compare it with every catalogue photo",
                  "buyer's photo", f"closest: {', '.join(tools.top_ids(run.image_scores, 3))}", t)

    t = time.perf_counter()
    run.photo = tools.describe_photo(run.img, vector)
    if run.photo["llm_failed"]:
        run.fallback_reasons.append("The AI could not describe the photo, so basic photo tags were used.")
    elif not run.photo["ai_available"]:
        run.fallback_reasons.append("No AI key is set, so the photo was described with basic tags.")
    run.trace.add("describe_photo", "Note the photo's pattern, border and shade, to explain each match",
                  "buyer's photo", _describe_tags(run.photo["tags"], run.photo["source"]), t)


def read_text(run):
    """Work out what the buyer asked for; ask a question back if it is too vague; then compare the request with the tags and (via CLIP) with the photos."""
    t = time.perf_counter()
    run.query = query = tools.parse_text_to_attributes(run.text)
    if query["llm_failed"]:
        run.fallback_reasons.append("The AI could not be reached, so the message was read with the keyword list.")
    elif query["source"] == "keywords":
        run.fallback_reasons.append("No AI key is set, so the message was read with the keyword list.")
    run.trace.add("parse_text_to_attributes", "Buyer sent text: work out what they are asking for",
                  run.text, _describe_query(query), t)

    if run.img is None and is_vague(query):
        run.mode = "vague"
        t = time.perf_counter()
        clarify = tools.ask_clarifying_question(run.text, query)
        if clarify["llm_failed"]:
            run.fallback_reasons.append("The AI could not write the question, so a standard one was used.")
        by = "Gemini" if clarify["source"] == "gemini" else "template"
        run.trace.add("ask_clarifying_question", "Too little to match on: ask the buyer one question",
                      run.text, f"{clarify['question']} (by {by})", t)
        run.clarifying_question = clarify["question"]

    if query["attributes"]:
        t = time.perf_counter()
        run.attr_scores = tools.attribute_filter(query["attributes"], run.designs.values())
        full = sum(1 for score, _ in run.attr_scores.values() if score == 1)
        run.trace.add("attribute_filter", "Compare the requested details with each design's tags",
                      query["attributes"], f"{full} of {len(run.designs)} designs match every detail", t)

    t = time.perf_counter()
    phrase = tools.english_phrase(query["attributes"], run.text)
    run.text_scores = tools.text_search(phrase)
    run.trace.add("text_search", "Compare the request in words with every catalogue photo",
                  phrase, f"closest: {', '.join(tools.top_ids(run.text_scores, 3))}", t)


def narrow_to_lookalikes(run):
    """Photo + text: the photo picks the design, the words only re-rank those lookalikes ("this design but in blue")."""
    if run.mode != "image_and_text":
        return list(run.designs)
    t = time.perf_counter()
    pool = tools.top_ids(run.image_scores, IMAGE_POOL)
    run.trace.add("narrow_to_lookalikes", "Photo and text: the photo picks the design, the words re-rank",
                  f"{len(run.designs)} designs", f"{len(pool)} that look most like the photo", t)
    return pool


def score_designs(run, pool):
    """One score per design: a weighted mix of the photo, tag and words scores."""
    weights = scoring.weights_for(run.mode, bool(run.image_scores), bool(run.attr_scores), bool(run.text_scores))
    scores = {}
    for design_id in pool:
        signals = {
            "image": run.image_scores.get(design_id, 0.0),
            "attributes": run.attr_scores.get(design_id, (0.0, []))[0],
            "text": run.text_scores.get(design_id, 0.0),
        }
        scores[design_id] = (scoring.combine(signals, weights), signals)
    return scores, weights


def check_stock_and_budget(run, pool, scores):
    """Stock and rate for the best candidates (only from stock.csv); drop anything over the buyer's budget."""
    ranked = sorted(pool, key=lambda d: -scores[d][0])[:CANDIDATES]
    t = time.perf_counter()
    max_rate = run.query["max_rate"]
    stock = tools.check_stock([run.designs[d] for d in ranked], max_rate, run.query["min_quantity"])
    over_budget = [d for d in ranked if not stock[d]["within_budget"]]
    kept = [d for d in ranked if stock[d]["within_budget"]][:TOP_K]
    got = f"{sum(stock[d]['in_stock'] for d in ranked)} of {len(ranked)} in stock"
    if max_rate:
        got += f"; {len(over_budget)} over ₹{max_rate:g} removed"
    run.trace.add("check_stock", "Read stock and rate from stock.csv for the best candidates",
                  f"top {len(ranked)} designs", got, t)
    return kept, stock, over_budget


def label_results(run, kept, scores, stock):
    """Label and explain each result."""
    asked = run.query["attributes"]
    # Only quote "same pattern/border" when Gemini described the photo; basic
    # CLIP photo tags are too rough to state as fact
    photo_tags = None
    if run.photo is not None:
        photo_tags = run.photo["tags"] if run.photo["source"] == "gemini" else {}

    results = []
    for design_id in kept:
        d = run.designs[design_id]
        score, signals = scores[design_id]
        matched = run.attr_scores.get(design_id, (0.0, []))[1]
        shade = None
        if run.photo is not None:
            shade = scoring.shade_difference(run.photo["colour"], tools.design_colour(d["image_file"]))
        label = scoring.label_for(score)
        if label == "very_close" and len(matched) < len(asked):
            label = "similar"  # "Very close" only when everything asked for matches
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
                "reason": scoring.reason_for(signals, d["tags"], asked, photo_tags, shade),
                "shade_note": scoring.needs_shade_note(asked, matched, shade, run.photo is not None),
                "matched_attributes": matched,
                **stock[design_id],
            }
        )

    # Nothing good enough, or too vague to judge: say so plainly. A vague
    # enquiry ("I want a saree") only gets best guesses, never "Very close".
    no_match = not results or results[0]["label"] == "none" or run.mode == "vague"
    if no_match:
        for r in results:
            r["label"] = "none"
            r["label_text"] = "Best guess" if run.mode == "vague" else "Nearest alternative"
    return results, no_match


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
