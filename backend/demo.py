"""Demo mode (DEMO_MODE=1): simulated WhatsApp buyers for presentations.

Each scenario goes through exactly the same code as a real WhatsApp message
(backend/inbox.py), only the message comes from here instead of Meta, and
replies are printed instead of sent. Photos are the edited "buyer-style"
copies in test_queries/.
"""

import threading
import time
import uuid

from backend import inbox
from backend.config import ROOT

SAMPLE_PHOTO_DIR = ROOT / "test_queries"

# (kind, value): "photo" = file in test_queries/, "text" = message text
SCENARIOS = [
    {
        "id": "ramesh",
        "buyer": "Ramesh Textiles",
        "place": "Surat",
        "phone": "910000000101",
        "language": "Photo + Hinglish",
        "messages": [("photo", "q_D010_text.jpg"), ("text", "isme blue silk wala chahiye, 20 piece")],
    },
    {
        "id": "meena",
        "buyer": "Meena Saree Centre",
        "place": "Jaipur",
        "phone": "910000000102",
        "language": "Hindi",
        "messages": [("text", "लाल बांधनी साड़ी चाहिए, 2000 तक")],
    },
    {
        "id": "patel",
        "buyer": "Patel Fabrics",
        "place": "Ahmedabad",
        "phone": "910000000103",
        "language": "Gujarati",
        "messages": [("text", "લાલ ઇકત કાપડ જોઈએ છે, ૨૦ પીસ")],
    },
    {
        "id": "kavita",
        "buyer": "Kavita Boutique",
        "place": "Mumbai",
        "phone": "910000000104",
        "language": "Photo only",
        "messages": [("photo", "q_D012.jpg")],
    },
    {
        "id": "sunil",
        "buyer": "Sunil Traders",
        "place": "Delhi",
        "phone": "910000000105",
        "language": "Messy Hinglish",
        "messages": [("text", "bandni wala georjet dupata laal colour mein 1500 tak")],
    },
    {
        "id": "anjali",
        "buyer": "Anjali",
        "place": "Pune",
        "phone": "910000000106",
        "language": "Vague",
        "messages": [("text", "kuch accha dikhao")],
    },
]


def public_scenarios():
    """What the screen needs to show the buttons."""
    out = []
    for s in SCENARIOS:
        photo = next((v for k, v in s["messages"] if k == "photo"), None)
        text = " ".join(v for k, v in s["messages"] if k == "text")
        out.append(
            {
                "id": s["id"],
                "buyer": s["buyer"],
                "place": s["place"],
                "language": s["language"],
                "text": text,
                "photo": photo,
            }
        )
    return out


def simulate(scenario_id):
    """Pretend the buyer messaged us. Runs in the background like a real webhook.
    Returns False for an unknown scenario."""
    scenario = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    if scenario is None:
        return False
    messages = []
    for kind, value in scenario["messages"]:
        base = {
            "id": f"wamid.DEMO{uuid.uuid4().hex[:16]}",
            "phone": scenario["phone"],
            "name": f"{scenario['buyer']} ({scenario['place']})",
            "timestamp": int(time.time()),
            "original_type": "image" if kind == "photo" else "text",
        }
        if kind == "photo":
            base.update(type="image", media_id=f"local:test_queries/{value}", text="")
        else:
            base.update(type="text", media_id=None, text=value)
        messages.append(base)
    threading.Thread(target=inbox.handle_messages, args=(messages,), daemon=True).start()
    return True


def sample_photos():
    """Buyer-style photos the Enquiry screen offers as one-tap examples."""
    return [p.name for p in sorted(SAMPLE_PHOTO_DIR.glob("q_*.jpg"))]
