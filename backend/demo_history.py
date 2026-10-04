"""A sample week of enquiries, so the Insights tab has something to show in a
demo. Every sample goes through the real agent (keyword list + CLIP, no AI
quota used); only the dates, buyers and replies are made up. Sample rows are
flagged (is_sample = 1), are never shown in the Inbox or Log, are labelled on
the Insights tab, and can be deleted with one button.

    python -m backend.demo_history          add a sample week
    python -m backend.demo_history --clear  remove it
"""

import argparse
import math
import random
from datetime import datetime, timedelta, timezone

from backend import db, enquiries, llm
from backend.agent import templates
from backend.config import ROOT
from backend.images import load_image_file

# What buyers typically ask a saree/fabric wholesaler, in their own words.
# Some match the sample stock well, some are things the shop does not have:
# that gap is what the "missed demand" panel is for.
SAMPLE_TEXTS = [
    ("lal bandhani chahiye", 3),
    ("red bandhani saree", 2),
    ("लाल बांधनी साड़ी 2000 तक", 2),
    ("blue bandhani dupatta cotton", 2),
    ("pink bandhani dupatta", 2),
    ("maroon patola saree", 2),
    ("black jamdani saree with gold zari", 2),
    ("orange bandhani georgette dupatta", 1),
    ("kanchipuram silk saree zari border", 1),
    ("phulkari dupatta pink", 1),
    ("mirror work dress material", 1),
    ("લાલ બાંધણી સાડી", 1),
    ("red silk saree paisley border", 2),
    ("green silk saree", 3),
    ("hara silk saree chahiye shaadi ke liye", 2),
    ("navy chiffon saree with silver border", 2),
    ("yellow lehenga", 2),
    ("peela lehenga chahiye", 1),
    ("white cotton kurti", 2),
    ("pink net lehenga", 1),
    ("black georgette saree under 1500", 1),
    ("red bandhani saree under 1000", 1),
    ("kuch naya dikhao", 1),
]
SAMPLE_PHOTOS = ["q_D007.jpg", "q_D016.jpg", "q_D020.jpg", "q_D009.jpg", "q_D012.jpg"]
BUYERS = [
    "Ramesh Textiles (Surat)", "Meena Saree Centre (Jaipur)", "Patel Fabrics (Ahmedabad)",
    "Kavita Boutique (Mumbai)", "Sunil Traders (Delhi)", "Laxmi Silks (Bengaluru)",
    "Gupta Cloth House (Kanpur)", "Shree Collection (Indore)",
]


def _sqlite(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _good_picks(answer):
    """Same rule as the screen: in-stock Very close / Similar, up to 2."""
    good = [r["design_id"] for r in answer["results"]
            if r["in_stock"] and r["label"] in ("very_close", "similar")]
    return good[:2]


def seed(count=42, days=7, seed_value=11):
    rng = random.Random(seed_value)
    texts = [t for t, weight in SAMPLE_TEXTS for _ in range(weight)]
    now = datetime.now(timezone.utc)
    made = 0
    with llm.offline():  # keyword list + CLIP only: fast and uses no AI quota
        for i in range(count):
            # Shop hours in India (9:30 to 20:30 IST = 4:00 to 15:00 UTC)
            day = now - timedelta(days=rng.randint(0, days - 1))
            when = day.replace(hour=4, minute=0, second=0) + timedelta(minutes=rng.randint(0, 660))
            if when > now:
                when = now - timedelta(minutes=rng.randint(5, 120))

            img, image_file, text = None, None, rng.choice(texts)
            if i % 7 == 3:  # some buyers send just a photo
                img = load_image_file(ROOT / "test_queries" / rng.choice(SAMPLE_PHOTOS))
                image_file, text = enquiries.save_upload(img), ""

            on_whatsapp = rng.random() < 0.7
            buyer = {"phone": f"91000{rng.randint(1000000, 9999999)}", "name": rng.choice(BUYERS),
                     "message_id": f"wamid.SAMPLE{i}"} if on_whatsapp else None
            answer = enquiries.run(text, img, image_file, whatsapp=buyer)
            enquiry_id = answer["enquiry_id"]

            # Most enquiries got a reply, typically within a few minutes
            picks = _good_picks(answer)
            replied = answer["mode"] != "vague" and rng.random() < 0.8
            with db.connect() as conn:
                conn.execute(
                    "UPDATE enquiries SET created_at = ?, is_sample = 1, status = ? WHERE id = ?",
                    (_sqlite(when), ("sent" if replied else "dismissed") if on_whatsapp else None, enquiry_id),
                )
            if replied:
                enquiry = db.get_enquiry(enquiry_id)
                designs = [db.get_design(d) for d in picks] or [db.get_design(answer["results"][0]["design_id"])]
                language = answer["query"]["language"] if answer["query"]["language"] in templates.LANGUAGES else "en"
                reply = templates.draft_reply(language, designs, no_match=answer["no_match"])
                audit_id = db.add_audit(enquiry, [d["design_id"] for d in designs], reply, language,
                                        sent_via="whatsapp" if on_whatsapp else "copy")
                minutes = min(90, max(1, round(math.exp(rng.gauss(1.8, 0.8)))))  # median about 6 min
                with db.connect() as conn:
                    conn.execute("UPDATE audit_log SET created_at = ?, is_sample = 1 WHERE id = ?",
                                 (_sqlite(when + timedelta(minutes=minutes)), audit_id))
            made += 1
    return made


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add or remove a sample week of enquiries")
    parser.add_argument("--clear", action="store_true")
    args = parser.parse_args()
    db.init_db()
    if args.clear:
        db.delete_samples()
        print("Sample history removed.")
    else:
        print(f"Added {seed()} sample enquiries.")
