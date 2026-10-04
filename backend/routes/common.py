"""Helpers used by more than one route file."""

import time

from fastapi import HTTPException
from fastapi.responses import FileResponse

from backend import db
from backend.config import CONFIG

WINDOW_HOURS = CONFIG["whatsapp"]["reply_window_hours"]


def file_inside(folder, name):
    """Serve folder/name, but never a file outside that folder (blocks "../" tricks)."""
    path = (folder / name).resolve()
    if path.parent != folder.resolve() or not path.is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(path)


def enquiry_and_picks(enquiry_id, picked):
    """The stored enquiry, after checking every picked design was on its shortlist."""
    enquiry = db.get_enquiry(enquiry_id)
    if enquiry is None:
        raise HTTPException(404, "Enquiry not found")
    if not set(picked) <= set(enquiry["shortlist"].get("ids", [])):
        raise HTTPException(400, "Pick designs from this enquiry's shortlist.")
    return enquiry


def hours_left(phone):
    """Hours left to reply freely on WhatsApp (0 = the 24-hour window has closed)."""
    last = db.last_message_time(phone)
    if not last:
        return 0
    return max(0.0, WINDOW_HOURS - (time.time() - last) / 3600)


def check_reply_text(text):
    text = text.strip()
    if not text:
        raise HTTPException(400, "The reply is empty.")
    if len(text) > 4000:
        raise HTTPException(400, "The reply is too long (over 4000 characters).")
    return text
