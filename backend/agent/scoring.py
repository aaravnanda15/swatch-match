"""Turns the three signals into one score per design.

    score = w_image * image_sim + w_attr * attr_match + w_text * text_sim

Each signal is between 0 and 1. Weights come from config.yaml and depend on
what the buyer sent.

Labels and one-line reasons are COMPUTED from scores, tags and a simple colour
check, never written by an LLM, so they cannot invent anything.
"""

from backend.config import CONFIG

SCORING = CONFIG["scoring"]

# Colours a buyer may call by a neighbour's name ("red" for a maroon saree).
# A near colour counts half.
NEAR_COLOURS = {
    "red": {"maroon", "orange", "pink"},
    "maroon": {"red", "brown", "purple"},
    "pink": {"red", "purple"},
    "orange": {"red", "yellow", "gold"},
    "yellow": {"gold", "orange", "cream"},
    "gold": {"yellow", "orange", "cream"},
    "blue": {"navy", "purple"},
    "navy": {"blue", "black"},
    "purple": {"pink", "blue", "maroon"},
    "white": {"cream", "silver", "grey"},
    "cream": {"white", "gold", "yellow"},
    "black": {"navy", "grey"},
    "grey": {"silver", "black", "white"},
    "silver": {"grey", "white"},
    "brown": {"maroon", "gold"},
    "green": set(),
    "multicolour": set(),
}

COLOUR_ATTRS = ("main_colour", "secondary_colour")


def stretch(value, low_high):
    """Map a raw similarity onto 0-1 using the range from config.yaml."""
    low, high = low_high
    return max(0.0, min(1.0, (value - low) / (high - low)))


def attribute_match(wanted, tags):
    """How well a design's tags fit what the buyer asked for.
    Returns (score 0-1, list of attributes that matched fully)."""
    if not wanted:
        return 0.0, []
    total, matched = 0.0, []
    for attr, value in wanted.items():
        have = tags.get(attr)
        if have == value:
            total += 1
            matched.append(attr)
        elif attr in COLOUR_ATTRS:
            # A colour can show up as either the main or the second colour
            other = tags.get("secondary_colour" if attr == "main_colour" else "main_colour")
            if other == value or have in NEAR_COLOURS.get(value, set()):
                total += 0.5
    return total / len(wanted), matched


def weights_for(mode, has_image, has_attributes, has_text):
    """Weights from config, with unused signals dropped and the rest scaled
    back up to add to 1 (e.g. text with no recognisable words relies on CLIP text only)."""
    key = "text_only" if mode == "vague" else mode
    weights = dict(SCORING["weights"][key])
    if not has_image:
        weights["image"] = 0.0
    if not has_attributes:
        weights["attributes"] = 0.0
    if not has_text:
        weights["text"] = 0.0
    total = sum(weights.values())
    if total == 0:
        # e.g. text-only enquiry with no known words: fall back to CLIP text
        return {"image": 0.0, "attributes": 0.0, "text": 1.0}
    return {k: v / total for k, v in weights.items()}


def combine(signals, weights):
    """signals: {"image": x, "attributes": y, "text": z} (missing = 0)."""
    return sum(weights[k] * signals.get(k, 0.0) for k in weights)


# ---------- labels ----------

LABELS = {
    "very_close": "Very close",
    "similar": "Similar",
    "alternative": "Alternative",
    "none": "Weak match",
}


def label_for(score):
    t = SCORING["thresholds"]
    if score >= t["very_close"]:
        return "very_close"
    if score >= t["similar"]:
        return "similar"
    if score >= t["alternative"]:
        return "alternative"
    return "none"


# ---------- one-line reasons ----------

ATTR_WORDS = {
    "garment_type": "type",
    "main_colour": "colour",
    "secondary_colour": "second colour",
    "pattern": "pattern",
    "border": "border",
    "fabric": "fabric",
    "work_type": "work",
}
MISS_ORDER = ("main_colour", "pattern", "garment_type", "fabric", "secondary_colour", "border", "work_type")
# Tag values that say nothing useful in a reason ("same border: none")
EMPTY_VALUES = {"none", "other", "unknown"}
# How much brighter/darker (0-1 scale) before we mention the shade
SHADE_STEP = 0.12


def _join(words):
    """["pattern", "border", "fabric"] -> "pattern, border and fabric"."""
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


def shade_difference(photo_colour, design_colour):
    """"darker", "lighter" or None, comparing the buyer's photo with a design photo."""
    if not photo_colour or not design_colour:
        return None
    diff = design_colour["brightness"] - photo_colour["brightness"]
    if diff <= -SHADE_STEP:
        return "darker"
    if diff >= SHADE_STEP:
        return "lighter"
    return None


def reason_for(signals, tags, asked, photo_tags, shade):
    """One short line explaining a match. photo_tags: tags of the buyer's photo
    ({} when they are too rough to quote, None when there is no photo). E.g.
    "Looks very similar to the photo: same pattern and border, shade darker"
    "Red bandhani saree as asked" / "Bandhani as asked, but blue instead of red"."""
    parts = []

    if photo_tags is not None:
        image = signals.get("image", 0)
        if image >= 0.75:
            look = "Looks very similar to the photo"
        elif image >= 0.45:
            look = "Similar look to the photo"
        else:
            look = "Different look from the photo"
        same = [ATTR_WORDS[a] for a in ("pattern", "border", "fabric", "work_type")
                if tags.get(a) and tags.get(a) == photo_tags.get(a) and tags.get(a) not in EMPTY_VALUES]
        parts.append(f"{look}: same {_join(same[:3])}" if same else look)

    if asked:
        got = [asked[a] for a in ("main_colour", "fabric", "pattern", "garment_type", "border", "work_type")
               if a in asked and tags.get(a) == asked[a]]
        # Differences buyers care about most come first: colour, then pattern...
        missed = [(a, asked[a]) for a in MISS_ORDER if a in asked and tags.get(a) != asked[a]]
        if got:
            parts.append(" ".join(got) + " as asked")
        for i, (attr, wanted) in enumerate(missed[:2]):
            have = tags.get(attr)
            but = "but " if got and i == 0 else ""
            if have and have not in EMPTY_VALUES:
                parts.append(f"{but}{have} instead of {wanted}")
            else:
                parts.append(f"{but}not {wanted}")

    if shade:
        parts.append(f"shade {shade}")

    line = ", ".join(parts) if parts else "Closest design in your catalogue"
    return line[0].upper() + line[1:]


def needs_shade_note(asked, matched, shade, has_photo):
    """Tell staff to double-check the shade when the photos differ in brightness,
    or (text enquiries) when colour carried most of the match: colours look
    different on every phone screen."""
    if shade:
        return True
    if has_photo:
        return False
    colour_hits = [a for a in matched if a in COLOUR_ATTRS]
    return bool(asked) and bool(colour_hits) and len(colour_hits) * 2 >= len(matched)
