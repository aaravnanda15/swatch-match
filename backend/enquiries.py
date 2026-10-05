"""Running an enquiry through the agent and saving it."""

import uuid

from backend import db
from backend.agent import orchestrator
from backend.config import UPLOAD_DIR
from backend.images import load_image_file, to_jpeg_bytes


def save_upload(img):
    image_file = f"{uuid.uuid4().hex}.jpg"
    (UPLOAD_DIR / image_file).write_bytes(to_jpeg_bytes(img))
    return image_file


def load_upload(image_file):
    return load_image_file(UPLOAD_DIR / image_file)


def _shortlist(answer):
    return {
        "ids": [r["design_id"] for r in answer["results"]],
        "no_match": answer["no_match"],
        "query": answer["query"],
        "question": answer["clarifying_question"],
    }


def run(text, img, image_file, whatsapp=None, display_text=None):
    """display_text: what the buyer actually wrote, when `text` is a combined request."""
    answer = orchestrator.handle_enquiry(text, img)
    answer["enquiry_id"] = db.create_enquiry(
        display_text if display_text is not None else text, image_file, answer["mode"], _shortlist(answer),
        answer=answer, whatsapp=whatsapp,
    )
    return answer


def rerun(enquiry_id, text, img, image_file):
    """Run an existing enquiry again with more information (photo + text merged)."""
    answer = orchestrator.handle_enquiry(text, img)
    answer["enquiry_id"] = enquiry_id
    db.update_enquiry(enquiry_id, text, image_file, answer["mode"], _shortlist(answer), answer)
    return answer
