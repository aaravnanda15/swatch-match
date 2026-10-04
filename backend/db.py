"""SQLite storage. One small file (data/swatch.db) holds everything.

Tables:
  designs     one row per catalogue design (from stock.csv)
  stock       quantity and rate, ONLY ever loaded from stock.csv
  tags        attribute tags per design, as JSON, plus where they came from
              ("gemini", "clip" or "manual" when staff corrected them)
  embeddings  CLIP image vector per design, stored as raw float32 bytes
  enquiries   one row per buyer enquiry (text, saved photo, enquiry type)
  audit_log   approved replies (filled in step 6)
"""

import json
import sqlite3

import numpy as np

from backend.config import DB_FILE

SCHEMA = """
CREATE TABLE IF NOT EXISTS designs (
    design_id  TEXT PRIMARY KEY,
    image_file TEXT NOT NULL,
    name       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stock (
    design_id          TEXT PRIMARY KEY REFERENCES designs(design_id),
    quantity_available INTEGER NOT NULL,
    rate               REAL NOT NULL,
    unit               TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tags (
    design_id  TEXT PRIMARY KEY REFERENCES designs(design_id),
    tags_json  TEXT NOT NULL,
    source     TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS embeddings (
    design_id  TEXT PRIMARY KEY REFERENCES designs(design_id),
    image_file TEXT NOT NULL,
    vector     BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS enquiries (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    text           TEXT,
    image_file     TEXT,
    mode           TEXT NOT NULL,
    shortlist_json TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    enquiry_text     TEXT,
    enquiry_image    TEXT,
    shortlist_json   TEXT,
    picked_json      TEXT,
    reply_text       TEXT,
    language         TEXT
);
"""


def connect():
    """Open the database. Use as `with connect() as conn:` so changes are saved."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)
        # Databases made before step 6 lack this column; add it in place
        columns = [r["name"] for r in conn.execute("PRAGMA table_info(enquiries)")]
        if "shortlist_json" not in columns:
            conn.execute("ALTER TABLE enquiries ADD COLUMN shortlist_json TEXT")


# ---------- designs and stock ----------

def upsert_design(conn, design_id, image_file, name, quantity, rate, unit):
    conn.execute(
        "INSERT INTO designs (design_id, image_file, name) VALUES (?, ?, ?) "
        "ON CONFLICT(design_id) DO UPDATE SET image_file = excluded.image_file, name = excluded.name",
        (design_id, image_file, name),
    )
    conn.execute(
        "INSERT INTO stock (design_id, quantity_available, rate, unit) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(design_id) DO UPDATE SET quantity_available = excluded.quantity_available, "
        "rate = excluded.rate, unit = excluded.unit",
        (design_id, quantity, rate, unit),
    )


def remove_designs_not_in(conn, keep_ids):
    """Designs deleted from stock.csv disappear from the app too."""
    rows = conn.execute("SELECT design_id FROM designs").fetchall()
    gone = [r["design_id"] for r in rows if r["design_id"] not in keep_ids]
    for design_id in gone:
        for table in ("tags", "embeddings", "stock", "designs"):
            conn.execute(f"DELETE FROM {table} WHERE design_id = ?", (design_id,))
    return gone


DESIGN_QUERY = """
SELECT d.design_id, d.image_file, d.name,
       s.quantity_available, s.rate, s.unit,
       t.tags_json, t.source AS tag_source
FROM designs d
JOIN stock s ON s.design_id = d.design_id
LEFT JOIN tags t ON t.design_id = d.design_id
"""


def _design_from_row(row):
    design = dict(row)
    design["tags"] = json.loads(design.pop("tags_json") or "{}")
    return design


def list_designs():
    with connect() as conn:
        rows = conn.execute(DESIGN_QUERY + " ORDER BY d.design_id").fetchall()
    return [_design_from_row(r) for r in rows]


def get_design(design_id):
    with connect() as conn:
        row = conn.execute(DESIGN_QUERY + " WHERE d.design_id = ?", (design_id,)).fetchone()
    return _design_from_row(row) if row else None


# ---------- tags ----------

def get_tag_source(conn, design_id):
    row = conn.execute("SELECT source FROM tags WHERE design_id = ?", (design_id,)).fetchone()
    return row["source"] if row else None


def save_tags(conn, design_id, tags, source):
    conn.execute(
        "INSERT INTO tags (design_id, tags_json, source, updated_at) VALUES (?, ?, ?, datetime('now')) "
        "ON CONFLICT(design_id) DO UPDATE SET tags_json = excluded.tags_json, "
        "source = excluded.source, updated_at = excluded.updated_at",
        (design_id, json.dumps(tags), source),
    )


# ---------- embeddings ----------

def get_embedding_file(conn, design_id):
    """Which photo the stored embedding was made from (None if no embedding yet)."""
    row = conn.execute("SELECT image_file FROM embeddings WHERE design_id = ?", (design_id,)).fetchone()
    return row["image_file"] if row else None


def save_embedding(conn, design_id, image_file, vector):
    conn.execute(
        "INSERT INTO embeddings (design_id, image_file, vector) VALUES (?, ?, ?) "
        "ON CONFLICT(design_id) DO UPDATE SET image_file = excluded.image_file, vector = excluded.vector",
        (design_id, image_file, np.asarray(vector, dtype=np.float32).tobytes()),
    )


def load_embeddings():
    """Return (list of design_ids, numpy matrix with one row per design)."""
    with connect() as conn:
        rows = conn.execute("SELECT design_id, vector FROM embeddings ORDER BY design_id").fetchall()
    ids = [r["design_id"] for r in rows]
    if not rows:
        return ids, np.zeros((0, 0), dtype=np.float32)
    matrix = np.vstack([np.frombuffer(r["vector"], dtype=np.float32) for r in rows])
    return ids, matrix


# ---------- enquiries ----------

def create_enquiry(text, image_file, mode, shortlist):
    """Save a new enquiry and what the agent found. Returns its id.
    shortlist = {"ids": [...], "no_match": bool, "query": {...}, "question": str|None}"""
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO enquiries (text, image_file, mode, shortlist_json) VALUES (?, ?, ?, ?)",
            (text or None, image_file, mode, json.dumps(shortlist)),
        )
        return cur.lastrowid


def get_enquiry(enquiry_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM enquiries WHERE id = ?", (enquiry_id,)).fetchone()
    if row is None:
        return None
    enquiry = dict(row)
    enquiry["shortlist"] = json.loads(enquiry.pop("shortlist_json") or "{}")
    return enquiry


# ---------- audit log (approved replies) ----------

def add_audit(enquiry, picked_ids, reply_text, language):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO audit_log (enquiry_text, enquiry_image, shortlist_json, picked_json, reply_text, language) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                enquiry["text"],
                enquiry["image_file"],
                json.dumps(enquiry["shortlist"].get("ids", [])),
                json.dumps(picked_ids),
                reply_text,
                language,
            ),
        )
        return cur.lastrowid


def list_audit(limit=200):
    """Newest first."""
    with connect() as conn:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    entries = []
    for row in rows:
        entry = dict(row)
        entry["shortlist"] = json.loads(entry.pop("shortlist_json") or "[]")
        entry["picked"] = json.loads(entry.pop("picked_json") or "[]")
        entries.append(entry)
    return entries
