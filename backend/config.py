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

# WhatsApp Business Cloud API (all four are needed; see README "Connect WhatsApp")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "").strip()
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip()
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "").strip()
# 1 = print messages instead of sending them (for testing without Meta)
WHATSAPP_DRY_RUN = os.getenv("WHATSAPP_DRY_RUN", "").strip() in ("1", "true", "yes")

# 1 = demo mode for presentations: the Inbox works without Meta (simulated
# buyers, replies never really sent) and sample data buttons are shown
DEMO_MODE = os.getenv("DEMO_MODE", "").strip() in ("1", "true", "yes")
ATTRIBUTES = CONFIG["attributes"]
