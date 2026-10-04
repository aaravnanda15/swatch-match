# Swatch Match for Hugging Face Spaces (Docker SDK, free CPU tier).
# Also runs anywhere Docker runs:
#   docker build -t swatch-match . && docker run -p 7860:7860 -e GEMINI_API_KEY=... swatch-match

# ---------- 1. Build the React UI ----------
FROM node:22-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- 2. The Python app ----------
FROM python:3.11-slim

# Hugging Face Spaces runs the container as user 1000
RUN useradd -m -u 1000 user
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/data/hf

# Small CPU-only PyTorch first, then everything else
COPY requirements.txt .
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install -r requirements.txt

COPY --chown=user . .
COPY --from=ui --chown=user /ui/dist frontend/dist
USER user

# Download the CLIP model and load the sample catalogue now, at build time,
# so the Space starts in seconds. Tags come from catalogue/tags.csv (or CLIP).
RUN python -m backend.ingest

EXPOSE 7860
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
