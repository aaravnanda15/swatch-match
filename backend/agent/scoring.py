"""Turns the three signals into one score per design.

    score = w_image * image_sim + w_attr * attr_match + w_text * text_sim

Each signal is between 0 and 1. Weights come from config.yaml and depend on
what the buyer sent. Labels, reasons and the shade note are added in step 4.
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
