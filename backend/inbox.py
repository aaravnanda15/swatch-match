"""Incoming WhatsApp messages -> enquiries in the Inbox.

Each message goes through the same agent as the Enquiry screen
(backend/enquiries.py). Buyers often send a photo and then a separate text
("isme blue chahiye"); messages from the same buyer within merge_seconds are
combined into one photo + text enquiry. Nothing is ever sent from here:
staff review the shortlist and tap Send in the app.
"""

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from backend import db, enquiries, whatsapp
from backend.config import CONFIG
from backend.images import BadImage, load_image

log = logging.getLogger("swatch.inbox")
MERGE_SECONDS = CONFIG["whatsapp"]["merge_seconds"]
MAX_TEXT = CONFIG["uploads"]["max_text_chars"]

# One message at a time, so a photo and the text right after it cannot race
_lock = threading.Lock()


def handle_messages(messages):
    """Called in the background after the webhook has already answered Meta."""
    for message in messages:
        try:
            with _lock:
                result = handle_message(message)
            log.info("%s from %s: %s", message["type"], mask(message["phone"]), result)
        except Exception:  # never let one bad message stop the others
            log.exception("failed on message %s", message.get("id"))


def handle_message(m):
    if not db.mark_seen(m["id"], m["phone"], int(time.time())):
        return "duplicate, ignored"
    buyer = {"phone": m["phone"], "name": m["name"], "message_id": m["id"]}
    text = (m["text"] or "").strip()[:MAX_TEXT]

    if m["type"] == "unsupported":
        note = f"[{m['original_type'] or 'message'}: not a photo or text]"
        db.add_chat(m["phone"], "in", text=note)
        return _save_unsupported(buyer, note)

    img, image_file = None, None
    if m["type"] == "image":
        try:
            # The buyer chat simulator hands over the photo directly
            data = m.get("image_bytes") or whatsapp.download_media(m["media_id"])
            img = load_image(data)
        except (whatsapp.WhatsAppError, BadImage) as e:
            note = f"[photo could not be used: {e}]"
            db.add_chat(m["phone"], "in", text=note)
            return _save_unsupported(buyer, note)
        image_file = enquiries.save_upload(img)

    if img is None and not text:
        return "empty, ignored"
    db.add_chat(m["phone"], "in", text=text or None, image_ref=f"upload:{image_file}" if image_file else None)

    # Same buyer, a moment ago, still waiting: merge photo and text
    since = (datetime.now(timezone.utc) - timedelta(seconds=MERGE_SECONDS)).strftime("%Y-%m-%d %H:%M:%S")
    previous = db.find_open_enquiry(m["phone"], since)
    if previous and previous["mode"] != "unsupported":
        if img is None and previous["image_file"] and not previous["text"]:
            photo = enquiries.load_upload(previous["image_file"])
            enquiries.rerun(previous["id"], text, photo, previous["image_file"])
            return f"text merged into enquiry #{previous['id']}"
        if img is not None and not previous["image_file"] and previous["text"]:
            combined = previous["text"] + (f" {text}" if text else "")
            enquiries.rerun(previous["id"], combined, img, image_file)
            return f"photo merged into enquiry #{previous['id']}"

    answer = enquiries.run(text, img, image_file, whatsapp=buyer)
    return f"new enquiry #{answer['enquiry_id']} ({answer['mode']})"


def _save_unsupported(buyer, note):
    enquiry_id = db.create_enquiry(note, None, "unsupported", {"ids": []}, answer=None, whatsapp=buyer)
    return f"saved as unsupported #{enquiry_id}"


def mask(phone):
    """910000000101 -> +91 00•••••101 (for logs and lists)."""
    phone = phone or ""
    if len(phone) < 8:
        return phone
    return f"+{phone[:2]} {phone[2:4]}•••••{phone[-3:]}"
