"""Running an enquiry through the agent and saving it. Shared by the Enquiry
screen (POST /api/enquiry) and WhatsApp messages (backend/inbox.py), so both
take exactly the same path.
"""

import uuid

from backend import db
from backend.agent import orchestrator
from backend.config import UPLOAD_DIR
from backend.images import load_image_file, to_jpeg_bytes


def save_upload(img):
    """Keep the buyer's (already cleaned) photo; returns its file name."""
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


def run(text, img, image_file, whatsapp=None):
    """Agent + save. Returns the agent's answer with "enquiry_id" added."""
    answer = orchestrator.handle_enquiry(text, img)
    answer["enquiry_id"] = db.create_enquiry(
        text, image_file, answer["mode"], _shortlist(answer), answer=answer, whatsapp=whatsapp
    )
    return answer


def rerun(enquiry_id, text, img, image_file):
    """Run an existing enquiry again with more information (photo + text merged)."""
    answer = orchestrator.handle_enquiry(text, img)
    answer["enquiry_id"] = enquiry_id
    db.update_enquiry(enquiry_id, text, image_file, answer["mode"], _shortlist(answer), answer)
    return answer
