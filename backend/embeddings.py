"""CLIP embeddings. Photos and text go into the same vector space, so we can
compare a buyer's photo OR words against catalogue photos.

The model (~600 MB) downloads once into data/models and is loaded the first
time it is needed, not at import time.
"""

import numpy as np

from backend.config import CONFIG, DATA_DIR

_model = None


def get_model():
    global _model
    if _model is None:
        # Imported here so the rest of the app starts fast and tests can run
        # without the big library.
        from sentence_transformers import SentenceTransformer

        print(f"Loading CLIP model {CONFIG['embeddings']['model']} (first time downloads ~600 MB)...")
        _model = SentenceTransformer(CONFIG["embeddings"]["model"], cache_folder=str(DATA_DIR / "models"))
    return _model


def encode_images(images):
    """List of PIL images -> numpy matrix, one normalised row per image."""
    vectors = get_model().encode(images, batch_size=16, convert_to_numpy=True, show_progress_bar=False)
    return _normalise(vectors)


def encode_texts(texts):
    """List of strings -> numpy matrix, one normalised row per text."""
    vectors = get_model().encode(texts, batch_size=64, convert_to_numpy=True, show_progress_bar=False)
    return _normalise(vectors)


def _normalise(vectors):
    vectors = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-8)
