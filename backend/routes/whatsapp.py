"""Inbox tab and WhatsApp: Meta's webhook, the list of WhatsApp enquiries, and sending an approved reply."""

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
    return {"items": items, "new": sum(1 for i in items if i["status"] == "new"), "filtered": db.filtered_total()}


@router.get("/inbox/ready")
def inbox_ready():
    """Every chat with a reply waiting for the seller, with enough context to approve it
    without opening the chat. Muted chats and replies already sent are left out."""
    ready = []
    for conv in db.list_conversations():
        state, out = conv["state"], conv["state"].get("outbox")
        if not out or not out.get("text") or state.get("flagged"):
            continue
        enquiry = db.get_enquiry(out["enquiry_id"])
        if enquiry is None or enquiry["source"] != "whatsapp" or enquiry["status"] != "new":
            continue
        chat = db.list_chat(conv["phone"])
        said = []  # what the buyer sent since our last message
        for m in reversed(chat):
            if m["direction"] != "in":
                break
            said.insert(0, {"text": m["text"], "image_ref": m["image_ref"]})
        designs = [db.get_design(d) for d in out["picked"]]
        ready.append({
            "enquiry_id": enquiry["id"],
            "buyer_name": enquiry["buyer_name"],
            "buyer_phone_masked": inbox.mask(conv["phone"]),
            "last_at": conv["updated_at"],
            "hours_left": round(hours_left(conv["phone"]), 1),
            "said": said[-4:] or [{"text": enquiry["text"], "image_ref": None}],
            "summary": state.get("summary", ""),
            "first_reply": not any(m["direction"] == "out" for m in chat),
            "text": out["text"],
            "picked": [{"design_id": d["design_id"], "name": d["name"], "image_file": d["image_file"]}
                       for d in designs if d],
            "language": out.get("language", "en"),
            "source": out.get("source"),
            "needs_staff": out.get("needs_staff", False),
        })
    ready.sort(key=lambda r: r["last_at"])  # oldest waiting first
    return {"items": ready}


@router.get("/inbox/{enquiry_id}")
def inbox_item(enquiry_id: int):
    enquiry = _whatsapp_enquiry(enquiry_id)
    answer = enquiry["answer"]
    if answer is not None:
        answer["enquiry_id"] = enquiry_id
    fields = ("created_at", "text", "image_file", "mode", "status", "sent_at", "buyer_name", "buyer_phone")
    # the chat bot's own first reply for this shortlist, so the reply box starts from it
    out = (db.get_conversation(enquiry["buyer_phone"]) or {}).get("outbox") or {}
    first_reply = out.get("enquiry_id") == enquiry_id and out.get("intent") == "new_or_changed_request"
    return {
        "id": enquiry_id,
        **{k: enquiry[k] for k in fields},
        "hours_left": round(hours_left(enquiry["buyer_phone"]), 1),
        "answer": answer,
        "followup": enquiry["followup"],
        "draft": {k: out.get(k) for k in ("text", "picked", "language", "source")} if first_reply else None,
    }


@router.get("/inbox/{enquiry_id}/chat")
def inbox_chat(enquiry_id: int):
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


class SendAllRequest(BaseModel):
    items: list[SendRequest]


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


@router.post("/whatsapp/send-all")
def whatsapp_send_all(req: SendAllRequest):
    """Reply to all: the seller approved every reply on the list in one go. Each one
    goes through the same checks as a single send; one failure doesn't stop the rest."""
    results = []
    for item in req.items:
        try:
            results.append({"enquiry_id": item.enquiry_id, "ok": True, **whatsapp_send(item)})
        except HTTPException as e:
            results.append({"enquiry_id": item.enquiry_id, "ok": False, "error": e.detail})
    return {"results": results, "sent": sum(1 for r in results if r["ok"])}
