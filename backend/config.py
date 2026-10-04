"""Loads config.yaml and the .env file once, so every other file can import them."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# The project root is one folder above this file (swatch-match/).
ROOT = Path(__file__).resolve().parent.parent

load_dotenv(ROOT / ".env")

with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

CATALOGUE_DIR = ROOT / CONFIG["paths"]["catalogue_dir"]
STOCK_CSV = ROOT / CONFIG["paths"]["stock_csv"]
DATA_DIR = ROOT / CONFIG["paths"]["data_dir"]
DB_FILE = ROOT / CONFIG["paths"]["db_file"]
UPLOAD_DIR = DATA_DIR / "uploads"
FRONTEND_DIST = ROOT / "frontend" / "dist"

DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
STAFF_PASSCODE = os.getenv("STAFF_PASSCODE", "").strip()  # empty = no login (local use)
ATTRIBUTES = CONFIG["attributes"]
