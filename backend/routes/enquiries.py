"""Enquiry tab and Log: run an enquiry, draft a reply, approve it, list approved replies."""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend import db, enquiries, insights
from backend.agent import templates, tools
from backend.config import CONFIG, UPLOAD_DIR
from backend.images import MAX_BYTES, BadImage, load_image
from backend.routes.common import check_reply_text, enquiry_and_picks, file_inside

router = APIRouter(prefix="/api")


@router.post("/enquiry")
def enquiry(image: UploadFile | None = File(None), text: str = Form("")):  # noqa: B008 (FastAPI style)
    """A buyer's enquiry: a photo, some text, or both."""
    text = text.strip()
    max_chars = CONFIG["uploads"]["max_text_chars"]
    if len(text) > max_chars:
        raise HTTPException(400, f"The message is too long. Please keep it under {max_chars} characters.")

    # Browsers send an empty file part when no photo was picked
    img, image_file = None, None
    if image is not None and image.filename:
        data = image.file.read(MAX_BYTES + 1)  # one byte too many, so "too big" is noticed
        try:
            img = load_image(data)
        except BadImage as e:
            raise HTTPException(400, str(e)) from e
        image_file = enquiries.save_upload(img)

    if image_file is None and not text:
        raise HTTPException(400, "Add a photo or type what the buyer asked for.")
    return enquiries.run(text, img, image_file)


class ReplyRequest(BaseModel):
    enquiry_id: int
    picked: list[str]
    language: str = "en"


@router.post("/reply")
def reply(req: ReplyRequest):
    """Draft reply for the picked designs. Stock and rate come from the database (stock.csv)."""
    if not req.picked:
        raise HTTPException(400, "Pick at least one design for the reply.")
    if req.language not in templates.LANGUAGES:
        raise HTTPException(400, "Unknown language.")
    shortlist = enquiry_and_picks(req.enquiry_id, req.picked)["shortlist"]
    text = tools.draft_reply(
        req.picked,
        req.language,
        no_match=shortlist.get("no_match", False),
        min_quantity=(shortlist.get("query") or {}).get("min_quantity"),
    )
    return {"text": text, "language": req.language}


class ApproveRequest(BaseModel):
    enquiry_id: int
    picked: list[str] = []
    text: str
    language: str = "en"


@router.post("/approve")
def approve(req: ApproveRequest):
    """Staff approved the (maybe edited) reply and will paste it themselves. Nothing is sent."""
    text = check_reply_text(req.text)
    enquiry = enquiry_and_picks(req.enquiry_id, req.picked)
    audit_id = db.add_audit(enquiry, req.picked, text, req.language)
    if enquiry["source"] == "whatsapp":
        db.set_status(enquiry["id"], "sent")
    return {"audit_id": audit_id}


@router.get("/audit")
def audit():
    return db.list_audit()


@router.get("/uploads/{image_file}")
def upload(image_file: str):
    """Buyer photos saved with each enquiry."""
    return file_inside(UPLOAD_DIR, image_file)


@router.get("/insights")
def insights_view(days: int = 7, tz_offset: int = 330):
    """Insights tab. tz_offset = the shop's minutes ahead of UTC (India: 330)."""
    return insights.compute(days=max(1, min(days, 90)), tz_offset_minutes=max(-720, min(tz_offset, 840)))
