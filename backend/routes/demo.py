"""Demo mode (DEMO_MODE=1): sample photos, simulated buyers, the sample Insights week, and the buyer chat page at /#buyer."""

import threading
import time
import uuid
from collections import defaultdict, deque

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend import db, demo, demo_history, inbox
from backend.config import CATALOGUE_DIR, CONFIG, DEMO_MODE, UPLOAD_DIR
from backend.images import MAX_BYTES, BadImage, load_image
from backend.routes.common import file_inside

router = APIRouter(prefix="/api/demo")

# The buyer chat routes are public (no passcode), so they only work in demo
# mode and are rate-limited per buyer.
CHAT_PREFIX = "9100"  # buyer chat numbers: 9100 + 8 digits, clearly not real mobiles
CHAT_LIMIT = 10  # messages per buyer per minute


def _demo_only():
    if not DEMO_MODE:
        raise HTTPException(404, "Demo mode is off")


@router.get("/photos")
def demo_photos():
    return demo.sample_photos()


@router.get("/photos/{name}")
def demo_photo(name: str):
    if name not in demo.sample_photos():
        raise HTTPException(404, "Not found")
    return file_inside(demo.SAMPLE_PHOTO_DIR, name)


@router.get("/scenarios")
def demo_scenarios():
    _demo_only()
    return demo.public_scenarios()


class SimulateRequest(BaseModel):
    scenario_id: str


@router.post("/simulate")
def demo_simulate(req: SimulateRequest):
    _demo_only()
    if not demo.simulate(req.scenario_id):
        raise HTTPException(404, "Unknown scenario")
    return {"ok": True}


@router.post("/history")
def demo_history_add():
    _demo_only()
    if db.count_samples() == 0:
        demo_history.seed()
    return {"sample_count": db.count_samples()}


@router.delete("/history")
def demo_history_clear():
    db.delete_samples()
    return {"sample_count": 0}


_recent = defaultdict(deque)
_recent_lock = threading.Lock()


def _check_chat_phone(phone):
    _demo_only()
    if not (phone.isdigit() and phone.startswith(CHAT_PREFIX) and len(phone) == 12):
        raise HTTPException(400, "Not a demo chat number")


def _rate_limit(phone):
    now = time.time()
    with _recent_lock:
        times = _recent[phone]
        while times and now - times[0] > 60:
            times.popleft()
        if len(times) >= CHAT_LIMIT:
            raise HTTPException(429, "Too many messages. Please wait a minute.")
        times.append(now)


@router.post("/chat/send")
def chat_send(
    phone: str = Form(...),
    name: str = Form(""),
    text: str = Form(""),
    image: UploadFile | None = File(None),  # noqa: B008 (FastAPI style)
):
    _check_chat_phone(phone)
    text = text.strip()[: CONFIG["uploads"]["max_text_chars"]]
    data = None
    if image is not None and image.filename:
        data = image.file.read(MAX_BYTES + 1)
        try:
            load_image(data)  # check now, so the buyer sees the error
        except BadImage as e:
            raise HTTPException(400, str(e)) from e
    if not data and not text:
        raise HTTPException(400, "Type a message or add a photo.")
    _rate_limit(phone)
    message = {
        "id": f"wamid.CHAT{uuid.uuid4().hex[:16]}",
        "phone": phone,
        "name": (name.strip() or "Buyer")[:60],
        "timestamp": int(time.time()),
        "type": "image" if data else "text",
        "original_type": "image" if data else "text",
        "text": text,
        "media_id": None,
        "image_bytes": data,
    }
    threading.Thread(target=inbox.handle_messages, args=([message],), daemon=True).start()
    return {"ok": True}


@router.get("/chat/{phone}")
def chat_messages(phone: str, after: int = 0):
    _check_chat_phone(phone)
    return [
        {
            "id": m["id"],
            "created_at": m["created_at"],
            "direction": m["direction"],
            "text": m["text"],
            "caption": m["caption"],
            "image_url": f"/api/demo/chat/image/{m['id']}" if m["image_ref"] else None,
        }
        for m in db.list_chat(phone, after)
    ]


@router.get("/chat/image/{message_id}")
def chat_image(message_id: int):
    _demo_only()
    m = db.get_chat_message(message_id)
    if not m or not m["image_ref"] or not m["phone"].startswith(CHAT_PREFIX):
        raise HTTPException(404, "Not found")
    kind, name = m["image_ref"].split(":", 1)
    return file_inside(UPLOAD_DIR if kind == "upload" else CATALOGUE_DIR, name)
