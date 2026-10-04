"""FastAPI app. All API routes live under /api; everything else serves the built React app."""

import threading
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import auth, db, demo, demo_history, embeddings, enquiries, inbox, insights, llm, stock_csv, whatsapp
from backend.agent import templates, tools
from backend.config import ATTRIBUTES, CATALOGUE_DIR, CONFIG, DEMO_MODE, FRONTEND_DIST, UPLOAD_DIR
from backend.images import MAX_BYTES, BadImage, load_image, load_image_file, to_jpeg_bytes
from backend.tagging import clean_tags


def _warm_up():
    """Load CLIP so the first enquiry is not slow; in demo mode also add the
    sample week if it is missing (Cloud Run starts with a fresh disk)."""
    embeddings.get_model()
    if DEMO_MODE and db.count_samples() == 0:
        print(f"[demo] added {demo_history.seed()} sample enquiries for the Insights tab")


@asynccontextmanager
async def lifespan(app):
    threading.Thread(target=_warm_up, daemon=True).start()
    yield


app = FastAPI(title="Swatch Match", lifespan=lifespan)
app.middleware("http")(auth.guard)  # staff passcode, only when STAFF_PASSCODE is set
db.init_db()


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "llm_configured": llm.get_llm().available,
        "designs": len(db.list_designs()),
        "login_required": auth.login_required(),
        "whatsapp_configured": whatsapp.enabled(),
        "whatsapp_dry_run": whatsapp.enabled() and whatsapp.dry_run(),
        "demo_mode": DEMO_MODE,
    }


class LoginRequest(BaseModel):
    passcode: str


@app.post("/api/login")
def login(req: LoginRequest, request: Request):
    if not auth.login_required():
        return {"ok": True}
    if not auth.passcode_ok(req.passcode.strip()):
        raise HTTPException(401, "Wrong passcode.")
    response = JSONResponse({"ok": True})
    auth.set_cookie(response, request)
    return response


@app.post("/api/logout")
def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(auth.COOKIE)
    return response


@app.get("/api/attributes")
def attributes():
    """The fixed tag vocabulary, so the tag editor can show dropdowns."""
    return ATTRIBUTES


@app.get("/api/settings")
def settings():
    """Upload limits, so the screen can warn before sending."""
    uploads = CONFIG["uploads"]
    return {
        "max_mb": uploads["max_mb"],
        "allowed_types": uploads["allowed_types"],
        "max_text_chars": uploads["max_text_chars"],
    }


@app.get("/api/designs")
def designs():
    return db.list_designs()


@app.patch("/api/designs/{design_id}/tags")
def update_tags(design_id: str, tags: dict):
    if db.get_design(design_id) is None:
        raise HTTPException(404, "Design not found")
    cleaned = clean_tags(tags)
    if cleaned is None:
        raise HTTPException(400, "Every tag must be one of the allowed values")
    with db.connect() as conn:
        db.save_tags(conn, design_id, cleaned, source="manual")
    return db.get_design(design_id)


@app.post("/api/enquiry")
def enquiry(image: UploadFile | None = File(None), text: str = Form("")):
    """A buyer's enquiry: a photo, some text, or both."""
    text = text.strip()
    max_chars = CONFIG["uploads"]["max_text_chars"]
    if len(text) > max_chars:
        raise HTTPException(400, f"The message is too long. Please keep it under {max_chars} characters.")

    # Browsers send an empty file part when no photo was picked; treat it as no photo.
    image_file, img = None, None
    if image is not None and image.filename:
        data = image.file.read(MAX_BYTES + 1)  # read one byte too many so "too big" is detected
        try:
            img = load_image(data)
        except BadImage as e:
            raise HTTPException(400, str(e))
        image_file = enquiries.save_upload(img)

    if image_file is None and not text:
        raise HTTPException(400, "Add a photo or type what the buyer asked for.")

    return enquiries.run(text, img, image_file)


class ReplyRequest(BaseModel):
    enquiry_id: int
    picked: list[str]
    language: str = "en"


class ApproveRequest(BaseModel):
    enquiry_id: int
    picked: list[str] = []
    text: str
    language: str = "en"


def _enquiry_and_picks(enquiry_id, picked):
    """The stored enquiry, after checking every picked design was on its shortlist."""
    enquiry = db.get_enquiry(enquiry_id)
    if enquiry is None:
        raise HTTPException(404, "Enquiry not found")
    allowed = set(enquiry["shortlist"].get("ids", []))
    if not set(picked) <= allowed:
        raise HTTPException(400, "Pick designs from this enquiry's shortlist.")
    return enquiry


@app.post("/api/reply")
def reply(req: ReplyRequest):
    """Draft reply for the picked designs. Numbers come from stock.csv via the database."""
    if not req.picked:
        raise HTTPException(400, "Pick at least one design for the reply.")
    if req.language not in templates.LANGUAGES:
        raise HTTPException(400, "Unknown language.")
    enquiry = _enquiry_and_picks(req.enquiry_id, req.picked)
    shortlist = enquiry["shortlist"]
    text = tools.draft_reply(
        req.picked,
        req.language,
        no_match=shortlist.get("no_match", False),
        min_quantity=(shortlist.get("query") or {}).get("min_quantity"),
    )
    return {"text": text, "language": req.language}


@app.post("/api/approve")
def approve(req: ApproveRequest):
    """Staff approved the (possibly edited) reply: record it. Nothing is sent to the buyer."""
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "The reply is empty.")
    if len(text) > 4000:
        raise HTTPException(400, "The reply is too long (over 4000 characters).")
    enquiry = _enquiry_and_picks(req.enquiry_id, req.picked)
    audit_id = db.add_audit(enquiry, req.picked, text, req.language)
    if enquiry["source"] == "whatsapp":
        db.set_status(enquiry["id"], "sent")  # staff will paste it into WhatsApp themselves
    return {"audit_id": audit_id}


@app.get("/api/audit")
def audit():
    return db.list_audit()


# ---------- WhatsApp ----------

@app.get("/api/whatsapp/webhook")
def whatsapp_verify(request: Request):
    """Meta's one-time check when the webhook URL is saved in its dashboard."""
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and whatsapp.verify_token_ok(q.get("hub.verify_token", "")):
        return PlainTextResponse(q.get("hub.challenge", ""))
    raise HTTPException(403, "Verification failed")


@app.post("/api/whatsapp/webhook")
async def whatsapp_receive(request: Request, background: BackgroundTasks):
    """New WhatsApp messages. Answer Meta at once; the agent runs in the background."""
    if not whatsapp.configured():
        raise HTTPException(404, "WhatsApp is not set up")
    raw = await request.body()
    if not whatsapp.verify_signature(raw, request.headers.get("x-hub-signature-256", "")):
        raise HTTPException(403, "Bad signature")
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(400, "Not JSON")
    messages = whatsapp.parse_webhook(payload)
    if messages:
        background.add_task(inbox.handle_messages, messages)
    return {"ok": True}


# ---------- Inbox (WhatsApp enquiries waiting for staff) ----------

WINDOW_HOURS = CONFIG["whatsapp"]["reply_window_hours"]


def _hours_left(phone):
    """Hours left to reply freely on WhatsApp (0 = window closed)."""
    last = db.last_message_time(phone)
    if not last:
        return 0
    return max(0.0, round(WINDOW_HOURS - (time.time() - last) / 3600, 1))


@app.get("/api/inbox")
def inbox_list():
    items = db.list_inbox()
    for item in items:
        item["buyer_phone_masked"] = inbox.mask(item.pop("buyer_phone"))
    return {"items": items, "new": sum(1 for i in items if i["status"] == "new")}


@app.get("/api/inbox/{enquiry_id}")
def inbox_item(enquiry_id: int):
    enquiry = db.get_enquiry(enquiry_id)
    if enquiry is None or enquiry["source"] != "whatsapp":
        raise HTTPException(404, "Not found")
    answer = enquiry["answer"]
    if answer is not None:
        answer["enquiry_id"] = enquiry_id
    return {
        "id": enquiry_id,
        "created_at": enquiry["created_at"],
        "text": enquiry["text"],
        "image_file": enquiry["image_file"],
        "mode": enquiry["mode"],
        "status": enquiry["status"],
        "sent_at": enquiry["sent_at"],
        "buyer_name": enquiry["buyer_name"],
        "buyer_phone": enquiry["buyer_phone"],
        "hours_left": _hours_left(enquiry["buyer_phone"]),
        "answer": answer,
    }


@app.post("/api/inbox/{enquiry_id}/dismiss")
def inbox_dismiss(enquiry_id: int):
    enquiry = db.get_enquiry(enquiry_id)
    if enquiry is None or enquiry["source"] != "whatsapp":
        raise HTTPException(404, "Not found")
    if enquiry["status"] == "sent":
        raise HTTPException(400, "Already replied.")
    db.set_status(enquiry_id, "dismissed")
    return {"ok": True}


class SendRequest(BaseModel):
    enquiry_id: int
    picked: list[str] = []
    text: str
    language: str = "en"


_send_lock = threading.Lock()  # two quick taps must not send twice


@app.post("/api/whatsapp/send")
def whatsapp_send(req: SendRequest):
    """Staff approved the reply: send the text, then a photo of each picked design."""
    if not whatsapp.enabled():
        raise HTTPException(404, "WhatsApp is not set up")
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "The reply is empty.")
    if len(text) > 4000:
        raise HTTPException(400, "The reply is too long for WhatsApp (over 4000 characters).")

    with _send_lock:
        enquiry = _enquiry_and_picks(req.enquiry_id, req.picked)
        if enquiry["source"] != "whatsapp":
            raise HTTPException(400, "This enquiry did not come from WhatsApp. Use Approve & copy.")
        if enquiry["status"] == "sent":
            raise HTTPException(409, "A reply was already sent for this enquiry.")
        if _hours_left(enquiry["buyer_phone"]) <= 0:
            raise HTTPException(
                400, "WhatsApp's 24-hour reply window has closed. Reply from your phone instead."
            )

        to = enquiry["buyer_phone"]
        # Buyers from the demo panel or the buyer chat page are never sent to Meta
        simulated = (enquiry["wa_message_id"] or "").startswith(("wamid.DEMO", "wamid.CHAT"))
        try:
            sent_ids = [whatsapp.send_text(to, text, simulated)]
        except whatsapp.WhatsAppError as e:
            raise HTTPException(502, str(e))  # nothing was sent; staff can try again
        db.add_chat(to, "out", text=text)

        # The text is out: from here on, record it even if a photo fails
        failed = []
        max_photos = CONFIG["whatsapp"]["max_photos"]
        for number, design_id in enumerate(req.picked[:max_photos], start=1):
            design = db.get_design(design_id)
            try:
                jpeg = to_jpeg_bytes(load_image_file(CATALOGUE_DIR / design["image_file"]))
                caption = f"{number}. {design['name']} ({design_id})"
                sent_ids.append(whatsapp.send_image(to, jpeg, f"{design_id}.jpg", caption, simulated))
                db.add_chat(to, "out", image_ref=f"catalogue:{design['image_file']}", caption=caption)
            except (whatsapp.WhatsAppError, BadImage, OSError) as e:
                failed.append({"design_id": design_id, "error": str(e)})

        db.set_status(enquiry["id"], "sent")
        audit_id = db.add_audit(
            enquiry, req.picked, text, req.language, sent_via="whatsapp", wa_sent_ids=sent_ids
        )
    return {
        "audit_id": audit_id,
        "messages_sent": len(sent_ids),
        "failed_photos": failed,
        "dry_run": whatsapp.dry_run() or simulated,
    }


# ---------- Insights ----------

@app.get("/api/insights")
def insights_view(days: int = 7, tz_offset: int = 330):
    """Numbers for the Insights tab. tz_offset = the shop's minutes ahead of UTC (India: 330)."""
    return insights.compute(days=max(1, min(days, 90)), tz_offset_minutes=tz_offset)


@app.post("/api/demo/history")
def demo_history_add():
    if not DEMO_MODE:
        raise HTTPException(404, "Demo mode is off")
    if db.count_samples() == 0:
        demo_history.seed()
    return {"sample_count": db.count_samples()}


@app.delete("/api/demo/history")
def demo_history_clear():
    db.delete_samples()
    return {"sample_count": 0}


# ---------- Demo helpers ----------

@app.get("/api/demo/photos")
def demo_photos():
    """Sample buyer photos for one-tap examples on the Enquiry screen."""
    return demo.sample_photos()


@app.get("/api/demo/photos/{name}")
def demo_photo(name: str):
    if name not in demo.sample_photos():
        raise HTTPException(404, "Not found")
    return FileResponse(demo.SAMPLE_PHOTO_DIR / name)


@app.get("/api/demo/scenarios")
def demo_scenarios():
    if not DEMO_MODE:
        raise HTTPException(404, "Demo mode is off")
    return demo.public_scenarios()


class SimulateRequest(BaseModel):
    scenario_id: str


@app.post("/api/demo/simulate")
def demo_simulate(req: SimulateRequest):
    """A pretend WhatsApp buyer messages the shop (demo mode only)."""
    if not DEMO_MODE:
        raise HTTPException(404, "Demo mode is off")
    if not demo.simulate(req.scenario_id):
        raise HTTPException(404, "Unknown scenario")
    return {"ok": True}


# ---------- Buyer chat simulator (demo mode) ----------
# A WhatsApp-style page at /#buyer: anyone can play a buyer from their own
# phone. Messages go through backend/inbox.py exactly like real WhatsApp, and
# the shop's replies (Send on WhatsApp) come back into the same chat.

CHAT_PREFIX = "9197"  # phone numbers of simulated chat buyers


def _demo_chat_only(phone=None):
    if not DEMO_MODE:
        raise HTTPException(404, "Demo mode is off")
    if phone is not None and not (phone.isdigit() and phone.startswith(CHAT_PREFIX) and 10 <= len(phone) <= 15):
        raise HTTPException(400, "Not a demo chat number")


@app.post("/api/demo/chat/send")
def demo_chat_send(
    phone: str = Form(...), name: str = Form(""), text: str = Form(""), image: UploadFile | None = File(None)
):
    _demo_chat_only(phone)
    text = text.strip()[: CONFIG["uploads"]["max_text_chars"]]
    data = None
    if image is not None and image.filename:
        data = image.file.read(MAX_BYTES + 1)
        try:
            load_image(data)  # check now so the buyer sees the error
        except BadImage as e:
            raise HTTPException(400, str(e))
    if not data and not text:
        raise HTTPException(400, "Type a message or add a photo.")
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


@app.get("/api/demo/chat/{phone}")
def demo_chat_messages(phone: str, after: int = 0):
    _demo_chat_only(phone)
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


@app.get("/api/demo/chat/image/{message_id}")
def demo_chat_image(message_id: int):
    _demo_chat_only()
    m = db.get_chat_message(message_id)
    if not m or not m["image_ref"] or not m["phone"].startswith(CHAT_PREFIX):
        raise HTTPException(404, "Not found")
    kind, name = m["image_ref"].split(":", 1)
    folder = UPLOAD_DIR if kind == "upload" else CATALOGUE_DIR
    path = (folder / name).resolve()
    if path.parent != folder.resolve() or not path.is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(path)


@app.get("/api/inbox/{enquiry_id}/chat")
def inbox_chat(enquiry_id: int):
    """The whole conversation with this enquiry's buyer (for the Inbox)."""
    enquiry = db.get_enquiry(enquiry_id)
    if enquiry is None or enquiry["source"] != "whatsapp":
        raise HTTPException(404, "Not found")
    return db.list_chat(enquiry["buyer_phone"])


@app.get("/api/uploads/{image_file}")
def upload(image_file: str):
    """Buyer photos saved with each enquiry (shown in the audit log)."""
    path = (UPLOAD_DIR / image_file).resolve()
    if path.parent != UPLOAD_DIR.resolve() or not path.is_file():
        raise HTTPException(404, "Image not found")
    return FileResponse(path)


class StockUpdate(BaseModel):
    quantity_available: int
    rate: float


@app.patch("/api/designs/{design_id}/stock")
def update_stock(design_id: str, update: StockUpdate):
    """Staff edit stock and rate. Saved to stock.csv first (the source of truth), then the database."""
    if db.get_design(design_id) is None:
        raise HTTPException(404, "Design not found")
    if not 0 <= update.quantity_available <= 1_000_000:
        raise HTTPException(400, "Stock must be a whole number from 0 to 1,000,000.")
    if not 0 < update.rate <= 10_000_000:
        raise HTTPException(400, "Rate must be more than ₹0.")
    rate = round(update.rate, 2)
    try:
        stock_csv.update_row(design_id, update.quantity_available, rate)
    except KeyError:
        raise HTTPException(400, "This design is not in stock.csv.")
    except OSError as e:
        raise HTTPException(500, f"Could not save stock.csv ({type(e).__name__}).")
    db.update_stock(design_id, update.quantity_available, rate)
    return db.get_design(design_id)


@app.get("/api/images/{image_file}")
def image(image_file: str):
    path = (CATALOGUE_DIR / image_file).resolve()
    # Only serve files that really sit inside catalogue/ (blocks "../" tricks).
    if path.parent != CATALOGUE_DIR.resolve() or not path.is_file():
        raise HTTPException(404, "Image not found")
    return FileResponse(path)


# Serve the React build (created by `npm run build`). Must be mounted last
# so it does not swallow the /api routes above.
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
