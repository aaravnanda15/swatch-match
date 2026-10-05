"""Nearest-neighbour search over the catalogue's CLIP vectors.

The vectors are kept in memory and reloaded only when the catalogue changes
(db.embeddings_version). A shop-sized catalogue is searched exactly with one
matrix multiply. Very large ones keep only the closest `top_n`, and above
`large_catalogue` designs an approximate HNSW index (faiss) is used if it is
installed.
"""

import logging
import threading

import numpy as np

from backend import db
from backend.config import CONFIG

log = logging.getLogger("swatch.search")
TOP_N = CONFIG["search"]["top_n"]
LARGE = CONFIG["search"]["large_catalogue"]

_lock = threading.Lock()
_state = {"version": None, "ids": [], "matrix": None, "ann": None}


def _current():
    version = db.embeddings_version()
    with _lock:
        if _state["version"] != version:
            ids, matrix = db.load_embeddings()
            _state.update(version=version, ids=ids, matrix=matrix, ann=_build_ann(matrix))
            log.info("loaded %d catalogue vectors%s", len(ids), " (HNSW index)" if _state["ann"] else "")
        return _state


def _build_ann(matrix):
    if len(matrix) <= LARGE:
        return None
    try:
        import faiss
    except ImportError:
        log.warning("%d designs but faiss is not installed; using exact search", len(matrix))
        return None
    index = faiss.IndexHNSWFlat(matrix.shape[1], 32, faiss.METRIC_INNER_PRODUCT)
    index.hnsw.efSearch = 128
    index.add(np.ascontiguousarray(matrix, dtype=np.float32))
    return index


def search(query):
    """{design_id: cosine similarity}, for every design in a normal catalogue
    and for the TOP_N closest in a very large one."""
    state = _current()
    ids, matrix, ann = state["ids"], state["matrix"], state["ann"]
    if not ids:
        return {}
    query = np.asarray(query, dtype=np.float32)
    if ann is not None:
        sims, rows = ann.search(query.reshape(1, -1), TOP_N)
        return {ids[r]: float(s) for r, s in zip(rows[0], sims[0], strict=True) if r >= 0}
    sims = matrix @ query
    if len(sims) > TOP_N:
        best = np.argpartition(-sims, TOP_N)[:TOP_N]
        return {ids[r]: float(sims[r]) for r in best}
    return dict(zip(ids, sims.tolist(), strict=True))
