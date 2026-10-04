"""Attribute tags for a catalogue photo.

First choice: ask the LLM (Gemini). If that is unavailable or fails, use CLIP
"zero-shot": compare the photo with short sentences like "a photo of a red
saree" and pick the closest sentence for each attribute.
"""

import numpy as np

from backend import embeddings, llm
from backend.config import ATTRIBUTES
from backend.images import to_jpeg_bytes

# Sentence templates for CLIP zero-shot tagging, one per attribute.
CLIP_TEMPLATES = {
    "garment_type": "a photo of a {}",
    "main_colour": "a photo of a mostly {} fabric",
    "secondary_colour": "a fabric with {} as the second colour",
    "pattern": "a fabric with a {} pattern",
    "border": "a saree with a {} border",
    "fabric": "a photo of {} fabric",
    "work_type": "a fabric decorated with {}",
}

# Some values read badly inside a sentence; give CLIP a clearer phrase.
CLIP_VALUE_TEXT = {
    ("secondary_colour", "none"): "a fabric with only one colour",
    ("border", "none"): "a fabric with no border",
    ("work_type", "none"): "a plain fabric with no decoration",
    ("fabric", "unknown"): "a photo of fabric",
    ("pattern", "other"): "a fabric with an unusual pattern",
    ("border", "other"): "a saree with an unusual border",
    ("work_type", "other"): "a fabric with unusual decoration",
    ("garment_type", "other"): "a photo of a textile product",
}


def clean_tags(raw):
    """Keep only known attributes with allowed values. Returns None if any
    attribute is missing or has a value outside the fixed vocabulary."""
    if not isinstance(raw, dict):
        return None
    cleaned = {}
    for attr, allowed in ATTRIBUTES.items():
        value = str(raw.get(attr, "")).strip().lower()
        if value not in allowed:
            return None
        cleaned[attr] = value
    return cleaned


def tag_with_llm(img):
    """Ask the LLM. Returns a dict of the valid values it gave (possibly partial),
    or None if the LLM is unavailable or answered nothing usable."""
    raw = llm.get_llm().tag_image(to_jpeg_bytes(img))
    if not isinstance(raw, dict):
        return None
    valid = {}
    for attr, allowed in ATTRIBUTES.items():
        value = str(raw.get(attr, "")).strip().lower()
        if value in allowed:
            valid[attr] = value
    return valid or None


def _clip_sentence(attr, value):
    return CLIP_VALUE_TEXT.get((attr, value), CLIP_TEMPLATES[attr].format(value))


# Text vectors for every attribute value, computed once and reused.
_text_vectors = {}


def _vectors_for(attr):
    if attr not in _text_vectors:
        sentences = [_clip_sentence(attr, v) for v in ATTRIBUTES[attr]]
        _text_vectors[attr] = embeddings.encode_texts(sentences)
    return _text_vectors[attr]


def tag_with_clip(image_vector):
    """Pick the closest value for each attribute using an already-computed image vector."""
    tags = {}
    for attr, values in ATTRIBUTES.items():
        scores = _vectors_for(attr) @ np.asarray(image_vector, dtype=np.float32)
        tags[attr] = values[int(np.argmax(scores))]
    return tags


def tag_image(img, image_vector):
    """Returns (tags, source) where source is "gemini" or "clip".
    If Gemini gives an odd value for one attribute, CLIP fills just that one."""
    llm_tags = tag_with_llm(img)
    clip_tags = tag_with_clip(image_vector)
    if not llm_tags:
        return clip_tags, "clip"
    tags = {attr: llm_tags.get(attr, clip_tags[attr]) for attr in ATTRIBUTES}
    # Call it a Gemini tag only if Gemini supplied most of the values.
    source = "gemini" if len(llm_tags) * 2 >= len(ATTRIBUTES) else "clip"
    return tags, source
