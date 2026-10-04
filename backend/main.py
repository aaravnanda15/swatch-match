"""FastAPI app. All API routes live under /api; everything else serves the built React app."""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import db, llm
from backend.config import ATTRIBUTES, CATALOGUE_DIR, FRONTEND_DIST
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
