"""Inbox tab and WhatsApp: Meta's webhook, the list of WhatsApp enquiries,
and sending an approved reply. Nothing is sent without a staff tap."""

import threading

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from backend import db, inbox, whatsapp
from backend.config import CATALOGUE_DIR, CONFIG
from backend.images import BadImage, load_image_file, to_jpeg_bytes
from backend.routes.common import check_reply_text, enquiry_and_picks, hours_left

router = APIRouter(prefix="/api")


@router.get("/whatsapp/webhook")
def whatsapp_verify(request: Request):
    """Meta's one-time check when the webhook URL is saved in its dashboard."""
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and whatsapp.verify_token_ok(q.get("hub.verify_token", "")):
        return PlainTextResponse(q.get("hub.challenge", ""))
    raise HTTPException(403, "Verification failed")


@router.post("/whatsapp/webhook")
async def whatsapp_receive(request: Request, background: BackgroundTasks):
    """New WhatsApp messages. Answer Meta at once; the agent runs in the background."""
    if not whatsapp.configured():
        raise HTTPException(404, "WhatsApp is not set up")
    raw = await request.body()
    if not whatsapp.verify_signature(raw, request.headers.get("x-hub-signature-256", "")):
        raise HTTPException(403, "Bad signature")
    try:
        payload = await request.json()
    except ValueError as e:
        raise HTTPException(400, "Not JSON") from e
    messages = whatsapp.parse_webhook(payload)
    if messages:
        background.add_task(inbox.handle_messages, messages)
    return {"ok": True}


def _whatsapp_enquiry(enquiry_id):
    enquiry = db.get_enquiry(enquiry_id)
    if enquiry is None or enquiry["source"] != "whatsapp":
        raise HTTPException(404, "Not found")
    return enquiry


@router.get("/inbox")
def inbox_list():
    items = db.list_inbox()
    for item in items:
        item["buyer_phone_masked"] = inbox.mask(item.pop("buyer_phone"))
    return {"items": items, "new": sum(1 for i in items if i["status"] == "new")}


@router.get("/inbox/{enquiry_id}")
def inbox_item(enquiry_id: int):
    enquiry = _whatsapp_enquiry(enquiry_id)
    answer = enquiry["answer"]
    if answer is not None:
        answer["enquiry_id"] = enquiry_id
    fields = ("created_at", "text", "image_file", "mode", "status", "sent_at", "buyer_name", "buyer_phone")
    return {
        "id": enquiry_id,
        **{k: enquiry[k] for k in fields},
        "hours_left": round(hours_left(enquiry["buyer_phone"]), 1),
        "answer": answer,
    }


@router.get("/inbox/{enquiry_id}/chat")
def inbox_chat(enquiry_id: int):
    """The whole conversation with this enquiry's buyer."""
    return db.list_chat(_whatsapp_enquiry(enquiry_id)["buyer_phone"])


@router.post("/inbox/{enquiry_id}/dismiss")
def inbox_dismiss(enquiry_id: int):
    if _whatsapp_enquiry(enquiry_id)["status"] == "sent":
        raise HTTPException(400, "Already replied.")
    db.set_status(enquiry_id, "dismissed")
    return {"ok": True}


class SendRequest(BaseModel):
    enquiry_id: int
    picked: list[str] = []
    text: str
    language: str = "en"


_send_lock = threading.Lock()  # two quick taps must not send twice


@router.post("/whatsapp/send")
def whatsapp_send(req: SendRequest):
    """Staff approved the reply: send the text, then a photo of each picked design."""
    if not whatsapp.enabled():
        raise HTTPException(404, "WhatsApp is not set up")
    text = check_reply_text(req.text)
    picked = list(dict.fromkeys(req.picked))  # same design twice = one photo

    with _send_lock:
        enquiry = enquiry_and_picks(req.enquiry_id, picked)
        if enquiry["source"] != "whatsapp":
            raise HTTPException(400, "This enquiry did not come from WhatsApp. Use Approve & copy.")
        if enquiry["status"] == "sent":
            raise HTTPException(409, "A reply was already sent for this enquiry.")
        if hours_left(enquiry["buyer_phone"]) <= 0:
            raise HTTPException(400, "WhatsApp's 24-hour reply window has closed. Reply from your phone instead.")

        to = enquiry["buyer_phone"]
        # Buyers from the demo panel or the buyer chat page are never sent to Meta
        simulated = (enquiry["wa_message_id"] or "").startswith(("wamid.DEMO", "wamid.CHAT"))
        try:
            sent_ids = [whatsapp.send_text(to, text, simulated)]
        except whatsapp.WhatsAppError as e:
            raise HTTPException(502, str(e)) from e  # nothing went out; staff can try again
        db.add_chat(to, "out", text=text)

        # The text is out, so from here on the send is recorded even if a photo fails
        failed = []
        for number, design_id in enumerate(picked[: CONFIG["whatsapp"]["max_photos"]], start=1):
            design = db.get_design(design_id)
            if design is None:  # removed from stock.csv since the shortlist was made
                failed.append({"design_id": design_id, "error": "no longer in the catalogue"})
                continue
            caption = f"{number}. {design['name']} ({design_id})"
            try:
                jpeg = to_jpeg_bytes(load_image_file(CATALOGUE_DIR / design["image_file"]))
                sent_ids.append(whatsapp.send_image(to, jpeg, f"{design_id}.jpg", caption, simulated))
                db.add_chat(to, "out", image_ref=f"catalogue:{design['image_file']}", caption=caption)
            except (whatsapp.WhatsAppError, BadImage, OSError) as e:
                failed.append({"design_id": design_id, "error": str(e)})

        db.set_status(enquiry["id"], "sent")
        audit_id = db.add_audit(enquiry, picked, text, req.language, sent_via="whatsapp", wa_sent_ids=sent_ids)
    return {
        "audit_id": audit_id,
        "messages_sent": len(sent_ids),
        "failed_photos": failed,
        "dry_run": whatsapp.dry_run() or simulated,
    }
