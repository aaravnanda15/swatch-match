"""Talks to Meta's WhatsApp Cloud API: webhook checks, parsing, media, sending.

WHATSAPP_DRY_RUN=1 prints instead of sending (see scripts/fake_whatsapp.py).
"""

import hashlib
import hmac
import logging
import uuid

import requests

from backend.config import (
    CONFIG,
    ROOT,
    DEMO_MODE,
    WHATSAPP_APP_SECRET,
    WHATSAPP_DRY_RUN,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_TOKEN,
    WHATSAPP_VERIFY_TOKEN,
)

log = logging.getLogger("swatch.whatsapp")
GRAPH = f"https://graph.facebook.com/{CONFIG['whatsapp']['api_version']}"
TIMEOUT = 20


class WhatsAppError(Exception):
    """A send or download failed. The message is safe to show to staff."""


def configured():
    """True when all four Meta settings are present (real webhook can be used)."""
    return all([WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_VERIFY_TOKEN, WHATSAPP_APP_SECRET])


def enabled():
    return configured() or DEMO_MODE


def dry_run():
    """Print instead of sending: asked for, or demo mode without real WhatsApp."""
    return WHATSAPP_DRY_RUN or not configured()


def verify_token_ok(token):
    """Meta's one-time webhook check: the token typed into Meta's dashboard must match ours."""
    return bool(WHATSAPP_VERIFY_TOKEN) and hmac.compare_digest(token.encode(), WHATSAPP_VERIFY_TOKEN.encode())


def verify_signature(raw_body: bytes, header: str):
    """Meta signs every webhook call with the app secret (X-Hub-Signature-256: sha256=<hex>)."""
    if not WHATSAPP_APP_SECRET or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(WHATSAPP_APP_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header[len("sha256="):], expected)


def parse_webhook(payload):
    """Meta's nested JSON -> list of simple dicts, one per incoming message: {"id", "phone", "name", "timestamp", "type", "text", "media_id"} type is "image", "text" or "unsupported" (video, voice note, sticker...)."""
    messages = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            names = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in value.get("contacts", []) or []}
            for m in value.get("messages", []) or []:
                kind = m.get("type")
                item = {
                    "id": m.get("id"),
                    "phone": m.get("from"),
                    "name": names.get(m.get("from")),
                    "timestamp": int(m.get("timestamp") or 0),
                    "type": "unsupported",
                    "text": "",
                    "media_id": None,
                    "original_type": kind,
                }
                if kind == "text":
                    item["type"] = "text"
                    item["text"] = (m.get("text") or {}).get("body", "")
                elif kind == "image":
                    item["type"] = "image"
                    item["media_id"] = (m.get("image") or {}).get("id")
                    item["text"] = (m.get("image") or {}).get("caption", "")
                if item["id"] and item["phone"]:
                    messages.append(item)
    return messages


def _headers():
    return {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}


def download_media(media_id):
    if dry_run() and media_id.startswith("local:"):
        path = (ROOT / media_id[len("local:"):]).resolve()
        if ROOT.resolve() not in path.parents or not path.is_file():
            raise WhatsAppError("Test photo not found.")
        return path.read_bytes()
    try:
        info = requests.get(f"{GRAPH}/{media_id}", headers=_headers(), timeout=TIMEOUT)
        info.raise_for_status()
        data = requests.get(info.json()["url"], headers=_headers(), timeout=TIMEOUT)
        data.raise_for_status()
        return data.content
    except (requests.RequestException, KeyError, ValueError) as e:
        raise WhatsAppError(f"Could not download the buyer's photo ({type(e).__name__}).") from e


def _post_message(body, simulated=False):
    if dry_run() or simulated:
        log.info("DRY RUN, not sent. To %s: %s %s", body["to"], body.get("type"), body.get("text") or body.get("image"))
        return f"dry-{uuid.uuid4().hex[:12]}"
    try:
        resp = requests.post(
            f"{GRAPH}/{WHATSAPP_PHONE_NUMBER_ID}/messages",
            headers=_headers(),
            json={"messaging_product": "whatsapp", **body},
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        raise WhatsAppError(f"Could not reach WhatsApp ({type(e).__name__}).") from e
    if resp.status_code >= 400:
        detail = ""
        try:
            detail = resp.json().get("error", {}).get("message", "")
        except ValueError:
            pass
        raise WhatsAppError(f"WhatsApp refused the message: {detail or resp.status_code}")
    return resp.json()["messages"][0]["id"]


def send_text(to, text, simulated=False):
    return _post_message({"to": to, "type": "text", "text": {"body": text, "preview_url": False}}, simulated)


def send_image(to, jpeg_bytes, filename, caption, simulated=False):
    if dry_run() or simulated:
        return _post_message({"to": to, "type": "image", "image": {"file": filename, "caption": caption}}, True)
    try:
        upload = requests.post(
            f"{GRAPH}/{WHATSAPP_PHONE_NUMBER_ID}/media",
            headers=_headers(),
            data={"messaging_product": "whatsapp", "type": "image/jpeg"},
            files={"file": (filename, jpeg_bytes, "image/jpeg")},
            timeout=TIMEOUT,
        )
        upload.raise_for_status()
        media_id = upload.json()["id"]
    except (requests.RequestException, KeyError, ValueError) as e:
        raise WhatsAppError(f"Could not upload {filename} to WhatsApp ({type(e).__name__}).") from e
    return _post_message({"to": to, "type": "image", "image": {"id": media_id, "caption": caption}})
