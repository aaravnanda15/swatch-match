"""FastAPI app. All API routes live under /api; everything else serves the built React app."""

import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import db, llm
from backend.config import ATTRIBUTES, CATALOGUE_DIR, CONFIG, FRONTEND_DIST, UPLOAD_DIR
from backend.images import MAX_BYTES, BadImage, load_image, to_jpeg_bytes
from backend.tagging import clean_tags

app = FastAPI(title="Swatch Match")
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
    image_file = None
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

    if image_file and text:
        mode = "image_and_text"
    elif image_file:
        mode = "image_only"
    else:
        mode = "text_only"
    enquiry_id = db.create_enquiry(text, image_file, mode)

    # Matching (agent tools) is added in step 3; for now just confirm receipt.
    return {
        "enquiry_id": enquiry_id,
        "mode": mode,
        "fallback_mode": not llm.get_llm().available,
        "results": [],
        "trace": [],
    }


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
