"""The FastAPI app."""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend import db, demo_history, embeddings, llm, whatsapp
from backend.config import DEMO_MODE, FRONTEND_DIST
from backend.images import MAX_BYTES
from backend.routes import catalogue, demo, enquiries, whatsapp as whatsapp_routes

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("swatch")

# Biggest request we accept: one photo at the size limit plus a little room for the form
MAX_REQUEST_BYTES = MAX_BYTES + 1024 * 1024


def _warm_up():
    embeddings.get_model()
    if DEMO_MODE and db.count_samples() == 0:
        log.info("added %d sample enquiries for the Insights tab", demo_history.seed())


@asynccontextmanager
async def lifespan(app):
    threading.Thread(target=_warm_up, daemon=True).start()
    yield


app = FastAPI(title="Swatch Match", lifespan=lifespan)
db.init_db()


@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    """Refuse huge uploads before reading them (the photo checks come later)."""
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_REQUEST_BYTES:
        return JSONResponse({"detail": "The upload is too big. Please send a photo under 10 MB."}, status_code=413)
    return await call_next(request)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "llm_configured": llm.get_llm().available,
        "designs": len(db.list_designs()),
        "whatsapp_configured": whatsapp.enabled(),
        "whatsapp_dry_run": whatsapp.enabled() and whatsapp.dry_run(),
        "demo_mode": DEMO_MODE,
    }


for routes in (catalogue, enquiries, whatsapp_routes, demo):
    app.include_router(routes.router)

# The React build (`npm run build`). Mounted last so it does not hide the /api routes.
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
