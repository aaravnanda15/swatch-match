"""FastAPI app. All API routes live under /api; everything else serves the built React app."""

import threading
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import db, embeddings, llm
from backend.agent import orchestrator, templates, tools
from backend.config import ATTRIBUTES, CATALOGUE_DIR, CONFIG, FRONTEND_DIST, UPLOAD_DIR
from backend.images import MAX_BYTES, BadImage, load_image, to_jpeg_bytes
from backend.tagging import clean_tags


@asynccontextmanager
async def lifespan(app):
    # Load CLIP in the background so the first enquiry is not slow
    threading.Thread(target=embeddings.get_model, daemon=True).start()
    yield


app = FastAPI(title="Swatch Match", lifespan=lifespan)
db.init_db()


@app.get("/api/health")
def health():
    return {"status": "ok", "llm_configured": llm.get_llm().available, "designs": len(db.list_designs())}


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
        image_file = f"{uuid.uuid4().hex}.jpg"
        (UPLOAD_DIR / image_file).write_bytes(to_jpeg_bytes(img))

    if image_file is None and not text:
        raise HTTPException(400, "Add a photo or type what the buyer asked for.")

    answer = orchestrator.handle_enquiry(text, img)
    shortlist = {
        "ids": [r["design_id"] for r in answer["results"]],
        "no_match": answer["no_match"],
        "query": answer["query"],
        "question": answer["clarifying_question"],
    }
    answer["enquiry_id"] = db.create_enquiry(text, image_file, answer["mode"], shortlist)
    return answer


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
