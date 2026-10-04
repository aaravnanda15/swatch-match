"""FastAPI app. All API routes live under /api; everything else serves the built React app."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.config import CONFIG, FRONTEND_DIST, GEMINI_API_KEY

app = FastAPI(title="Swatch Match")


@app.get("/api/health")
def health():
    llm_on = CONFIG["llm"]["provider"] != "none" and bool(GEMINI_API_KEY)
    return {"status": "ok", "llm_configured": llm_on}


# Serve the React build (created by `npm run build`). Must be mounted last
# so it does not swallow the /api routes above.
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
