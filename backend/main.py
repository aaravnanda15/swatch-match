"""FastAPI app. All API routes live under /api; everything else serves the built React app."""

import threading
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import auth, db, embeddings, enquiries, inbox, llm, whatsapp
from backend.agent import templates, tools
from backend.config import ATTRIBUTES, CATALOGUE_DIR, CONFIG, FRONTEND_DIST, UPLOAD_DIR
from backend.images import MAX_BYTES, BadImage, load_image
from backend.tagging import clean_tags


@asynccontextmanager
async def lifespan(app):
    # Load CLIP in the background so the first enquiry is not slow
    threading.Thread(target=embeddings.get_model, daemon=True).start()
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
        "whatsapp_configured": whatsapp.configured(),
        "whatsapp_dry_run": whatsapp.configured() and whatsapp.dry_run(),
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


@app.get("/api/uploads/{image_file}")
def upload(image_file: str):
    """Buyer photos saved with each enquiry (shown in the audit log)."""
    path = (UPLOAD_DIR / image_file).resolve()
    if path.parent != UPLOAD_DIR.resolve() or not path.is_file():
        raise HTTPException(404, "Image not found")
    return FileResponse(path)


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
