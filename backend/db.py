"""SQLite storage. One small file (data/swatch.db) holds everything.

Tables:
  designs     one row per catalogue design (from stock.csv)
  stock       quantity and rate, ONLY ever loaded from stock.csv
  tags        attribute tags per design, as JSON, plus where they came from
              ("gemini", "clip" or "manual" when staff corrected them)
  embeddings  CLIP image vector per design, stored as raw float32 bytes
  enquiries   one row per buyer enquiry (text, saved photo, enquiry type, the
              agent's answer; WhatsApp enquiries also have the buyer and a status)
  wa_seen     every WhatsApp message id received, so Meta's retries are ignored
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
CREATE TABLE IF NOT EXISTS wa_seen (
    message_id  TEXT PRIMARY KEY,
    phone       TEXT NOT NULL,
    received_at INTEGER NOT NULL      -- unix seconds
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


# Columns added after the first version. Older databases get them on start-up.
NEW_COLUMNS = {
    "enquiries": {
        "shortlist_json": "TEXT",
        "answer_json": "TEXT",  # full agent answer, so the Inbox can show it again
        "source": "TEXT NOT NULL DEFAULT 'app'",  # 'app' or 'whatsapp'
        "buyer_phone": "TEXT",
        "buyer_name": "TEXT",
        "wa_message_id": "TEXT",
        "status": "TEXT",  # WhatsApp only: 'new', 'sent' or 'dismissed'
        "sent_at": "TEXT",
    },
    "audit_log": {
        "sent_via": "TEXT NOT NULL DEFAULT 'copy'",  # 'copy' or 'whatsapp'
        "wa_sent_ids": "TEXT",
        "enquiry_id": "INTEGER",
    },
}


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)
        for table, columns in NEW_COLUMNS.items():
            have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            for name, kind in columns.items():
                if name not in have:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {kind}")


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

def create_enquiry(text, image_file, mode, shortlist, answer=None, whatsapp=None):
    """Save a new enquiry and what the agent found. Returns its id.
    shortlist = {"ids": [...], "no_match": bool, "query": {...}, "question": str|None}
    whatsapp  = {"phone", "name", "message_id"} for enquiries that came in on WhatsApp"""
    wa = whatsapp or {}
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO enquiries (text, image_file, mode, shortlist_json, answer_json, source, "
            "buyer_phone, buyer_name, wa_message_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                text or None,
                image_file,
                mode,
                json.dumps(shortlist),
                json.dumps(answer) if answer is not None else None,
                "whatsapp" if whatsapp else "app",
                wa.get("phone"),
                wa.get("name"),
                wa.get("message_id"),
                "new" if whatsapp else None,
            ),
        )
        return cur.lastrowid


def update_enquiry(enquiry_id, text, image_file, mode, shortlist, answer):
    """Replace an enquiry's content (used when a buyer's photo and text arrive separately)."""
    with connect() as conn:
        conn.execute(
            "UPDATE enquiries SET text = ?, image_file = ?, mode = ?, shortlist_json = ?, answer_json = ? WHERE id = ?",
            (text or None, image_file, mode, json.dumps(shortlist), json.dumps(answer), enquiry_id),
        )


def _enquiry_from_row(row):
    enquiry = dict(row)
    enquiry["shortlist"] = json.loads(enquiry.pop("shortlist_json") or "{}")
    enquiry["answer"] = json.loads(enquiry.pop("answer_json") or "null")
    return enquiry


def get_enquiry(enquiry_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM enquiries WHERE id = ?", (enquiry_id,)).fetchone()
    return _enquiry_from_row(row) if row else None


# ---------- WhatsApp inbox ----------

def mark_seen(message_id, phone, received_at):
    """Remember a WhatsApp message. Returns False if it was already seen (a retry)."""
    with connect() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO wa_seen (message_id, phone, received_at) VALUES (?, ?, ?)",
            (message_id, phone, received_at),
        )
        return cur.rowcount == 1


def last_message_time(phone):
    """Unix time of the buyer's latest message (for WhatsApp's 24-hour reply window)."""
    with connect() as conn:
        row = conn.execute("SELECT MAX(received_at) AS t FROM wa_seen WHERE phone = ?", (phone,)).fetchone()
    return row["t"]


def find_open_enquiry(phone, since_sqlite_time):
    """The buyer's latest WhatsApp enquiry still waiting for staff, if it is recent."""
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM enquiries WHERE source = 'whatsapp' AND buyer_phone = ? AND status = 'new' "
            "AND created_at >= ? ORDER BY id DESC LIMIT 1",
            (phone, since_sqlite_time),
        ).fetchone()
    return _enquiry_from_row(row) if row else None


def list_inbox(limit=100):
    """WhatsApp enquiries, newest first, without the bulky answer."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, created_at, text, image_file, mode, buyer_phone, buyer_name, status, sent_at "
            "FROM enquiries WHERE source = 'whatsapp' ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def set_status(enquiry_id, status):
    with connect() as conn:
        if status == "sent":
            conn.execute("UPDATE enquiries SET status = 'sent', sent_at = datetime('now') WHERE id = ?", (enquiry_id,))
        else:
            conn.execute("UPDATE enquiries SET status = ? WHERE id = ?", (status, enquiry_id))


# ---------- audit log (approved replies) ----------

def add_audit(enquiry, picked_ids, reply_text, language, sent_via="copy", wa_sent_ids=None):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO audit_log (enquiry_text, enquiry_image, shortlist_json, picked_json, reply_text, language, "
            "sent_via, wa_sent_ids, enquiry_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                enquiry["text"],
                enquiry["image_file"],
                json.dumps(enquiry["shortlist"].get("ids", [])),
                json.dumps(picked_ids),
                reply_text,
                language,
                sent_via,
                json.dumps(wa_sent_ids) if wa_sent_ids else None,
                enquiry["id"],
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
