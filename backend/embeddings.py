"""CLIP embeddings."""

import threading

import numpy as np

from backend.config import CONFIG, DATA_DIR

_model = None
_lock = threading.Lock()  # the server warms the model in the background; load it only once


def get_model():
    global _model
    with _lock:
        if _model is None:
            # Imported here so the rest of the app starts fast and tests can run
            # without the big library.
            from sentence_transformers import SentenceTransformer

            print(f"Loading CLIP model {CONFIG['embeddings']['model']} (first time downloads ~600 MB)...")
            _model = SentenceTransformer(CONFIG["embeddings"]["model"], cache_folder=str(DATA_DIR / "models"))
    return _model


def encode_images(images):
    vectors = get_model().encode(images, batch_size=16, convert_to_numpy=True, show_progress_bar=False)
    return _normalise(vectors)


def encode_texts(texts):
    vectors = get_model().encode(texts, batch_size=64, convert_to_numpy=True, show_progress_bar=False)
    return _normalise(vectors)


def _normalise(vectors):
    vectors = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-8)
