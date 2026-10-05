"""Catalogue tab: designs, tags, stock and price, and the design photos."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend import conversation, db, inbox, stock_csv
from backend.config import ATTRIBUTES, CATALOGUE_DIR, CONFIG
from backend.routes.common import file_inside
from backend.tagging import clean_tags

router = APIRouter(prefix="/api")


@router.get("/attributes")
def attributes():
    return ATTRIBUTES


@router.get("/settings")
def settings():
    uploads = CONFIG["uploads"]
    return {
        "max_mb": uploads["max_mb"],
        "allowed_types": uploads["allowed_types"],
        "max_text_chars": uploads["max_text_chars"],
    }


@router.get("/designs")
def designs():
    return db.list_designs()


@router.patch("/designs/{design_id}/tags")
def update_tags(design_id: str, tags: dict):
    if db.get_design(design_id) is None:
        raise HTTPException(404, "Design not found")
    cleaned = clean_tags(tags)
    if cleaned is None:
        raise HTTPException(400, "Every tag must be one of the allowed values")
    with db.connect() as conn:
        db.save_tags(conn, design_id, cleaned, source="manual")
    return db.get_design(design_id)


class StockUpdate(BaseModel):
    quantity_available: int
    rate: float


@router.patch("/designs/{design_id}/stock")
def update_stock(design_id: str, update: StockUpdate):
    """Staff edit stock and rate. Back in stock = a draft for every buyer who wanted it."""
    old = db.get_design(design_id)
    if old is None:
        raise HTTPException(404, "Design not found")
    if not 0 <= update.quantity_available <= 1_000_000:
        raise HTTPException(400, "Stock must be a whole number from 0 to 1,000,000.")
    if not 0 < update.rate <= 10_000_000:
        raise HTTPException(400, "Rate must be more than ₹0.")
    rate = round(update.rate, 2)
    try:
        stock_csv.update_row(design_id, update.quantity_available, rate)
    except KeyError as e:
        raise HTTPException(400, "This design is not in stock.csv.") from e
    except OSError as e:
        raise HTTPException(500, f"Could not save stock.csv ({type(e).__name__}).") from e
    db.update_stock(design_id, update.quantity_available, rate)
    drafted = 0
    if old["quantity_available"] <= 0 < update.quantity_available:
        with inbox.lock:
            drafted = conversation.back_in_stock(design_id)
    return {**db.get_design(design_id), "back_in_stock_drafts": drafted}


@router.get("/images/{image_file}")
def image(image_file: str):
    return file_inside(CATALOGUE_DIR, image_file)
