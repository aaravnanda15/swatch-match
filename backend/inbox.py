"""Incoming WhatsApp messages -> enquiries in the Inbox."""

import logging
import threading
import time

from backend import conversation, db, enquiries, whatsapp
from backend.config import CONFIG
from backend.images import BadImage, load_image

log = logging.getLogger("swatch.inbox")
MAX_TEXT = CONFIG["uploads"]["max_text_chars"]

# One message at a time, so a photo and the text right after it cannot race
lock = threading.Lock()


def handle_messages(messages):
    for message in messages:
        try:
            with lock:
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

    # the chat keeps its own state; see backend/conversation.py
    turn = conversation.handle_turn(m["phone"], m["name"], text, img, image_file, buyer)
    return f"{turn['intent']} (read by {turn['read_by']}), enquiry #{turn['state']['enquiry_id']}"


def _save_unsupported(buyer, note):
    enquiry_id = db.create_enquiry(note, None, "unsupported", {"ids": []}, answer=None, whatsapp=buyer)
    return f"saved as unsupported #{enquiry_id}"


def mask(phone):
    phone = phone or ""
    if len(phone) < 8:
        return phone
    return f"+{phone[:2]} {phone[2:4]}•••••{phone[-3:]}"
