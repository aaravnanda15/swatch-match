"""Pretend to be Meta: send a WhatsApp message to the local webhook.

For testing the Inbox without a Meta account. The server must run with
WHATSAPP_DRY_RUN=1 (so photos are read from disk and replies are printed,
not sent) and the four WHATSAPP_* settings filled in with any test values.

    python scripts/fake_whatsapp.py --photo test_queries/q_D010_text.jpg
    python scripts/fake_whatsapp.py --text "isme blue chahiye"
    python scripts/fake_whatsapp.py --photo test_queries/q_D012.jpg --text "same in red"   (photo with caption)
    python scripts/fake_whatsapp.py --voice                (an unsupported message type)
    python scripts/fake_whatsapp.py --text hi --id wamid.X --id-again   (send the same message twice)
    python scripts/fake_whatsapp.py --text hi --bad-signature           (should be refused with 403)
"""

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def build_payload(args, message_id):
    message = {"from": args.phone, "id": message_id, "timestamp": str(int(time.time()))}
    if args.voice:
        message.update(type="audio", audio={"id": "fake-audio", "mime_type": "audio/ogg"})
    elif args.photo:
        image = {"id": f"local:{args.photo}", "mime_type": "image/jpeg"}
        if args.text:
            image["caption"] = args.text
        message.update(type="image", image=image)
    else:
        message.update(type="text", text={"body": args.text})
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "TEST_WABA",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "15550000000", "phone_number_id": "TEST"},
                            "contacts": [{"profile": {"name": args.name}, "wa_id": args.phone}],
                            "messages": [message],
                        },
                    }
                ],
            }
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--photo", help="path of a photo inside the project, e.g. test_queries/q_D012.jpg")
    parser.add_argument("--text", default="", help="message text (or the photo caption)")
    parser.add_argument("--voice", action="store_true", help="send a voice note (unsupported type)")
    parser.add_argument("--phone", default="919800000001")
    parser.add_argument("--name", default="Test Buyer")
    parser.add_argument("--id", help="WhatsApp message id (default: random)")
    parser.add_argument("--id-again", action="store_true", help="send the same message twice, like a Meta retry")
    parser.add_argument("--bad-signature", action="store_true")
    parser.add_argument("--url", default="http://localhost:7860/api/whatsapp/webhook")
    args = parser.parse_args()
    if not (args.photo or args.text or args.voice):
        sys.exit("Give --photo, --text or --voice.")

    secret = os.getenv("WHATSAPP_APP_SECRET", "")
    if not secret:
        sys.exit("WHATSAPP_APP_SECRET is empty in .env.")

    message_id = args.id or f"wamid.TEST{uuid.uuid4().hex[:16]}"
    body = json.dumps(build_payload(args, message_id)).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if args.bad_signature:
        signature = "0" * 64
    headers = {"Content-Type": "application/json", "X-Hub-Signature-256": f"sha256={signature}"}

    for attempt in range(2 if args.id_again else 1):
        resp = requests.post(args.url, data=body, headers=headers, timeout=30)
        print(f"sent {message_id} -> {resp.status_code} {resp.text[:100]}")


if __name__ == "__main__":
    main()
