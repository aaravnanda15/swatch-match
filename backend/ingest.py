"""Load the catalogue into SQLite.

    python -m backend.ingest            add new designs, refresh stock and rates
    python -m backend.ingest --retag    re-tag every design (keeps staff edits)

Steps: read stock.csv -> save designs + stock -> staff tags from the optional
catalogue/tags.csv -> CLIP embedding for each new photo -> tags (Gemini, or
CLIP fallback) for each design still untagged.
Safe to run again: work already done is skipped.
"""

import argparse
import csv
import sys
import time

from backend import db, embeddings, llm, tagging
from backend.config import CATALOGUE_DIR, CONFIG, STOCK_CSV
from backend.images import BadImage, load_image_file

REQUIRED_COLUMNS = ["design_id", "image_file", "name", "quantity_available", "rate", "unit"]


def read_stock_csv():
    """Return a list of clean rows. Bad rows are skipped with a warning, never guessed."""
    if not STOCK_CSV.exists():
        sys.exit(f"Missing {STOCK_CSV}. Run scripts/fetch_sample_catalogue.py first.")
    with open(STOCK_CSV, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            sys.exit(f"stock.csv is missing columns: {', '.join(missing)}")
        rows, seen = [], set()
        for line_no, row in enumerate(reader, start=2):
            design_id = (row["design_id"] or "").strip()
            image_file = (row["image_file"] or "").strip()
            try:
                quantity = int(float(row["quantity_available"]))
                rate = float(row["rate"])
            except (TypeError, ValueError):
                print(f"  ! line {line_no}: quantity or rate is not a number, skipped")
                continue
            if quantity < 0 or rate <= 0:
                print(f"  ! line {line_no}: stock below 0 or rate not above 0, skipped")
                continue
            if not design_id or design_id in seen:
                print(f"  ! line {line_no}: empty or duplicate design_id, skipped")
                continue
            if not (CATALOGUE_DIR / image_file).is_file():
                print(f"  ! line {line_no}: photo {image_file!r} not found in catalogue/, skipped")
                continue
            try:
                load_image_file(CATALOGUE_DIR / image_file)
            except BadImage as e:
                print(f"  ! line {line_no}: {image_file}: {e} Skipped.")
                continue
            seen.add(design_id)
            rows.append(
                {
                    "design_id": design_id,
                    "image_file": image_file,
                    "name": (row["name"] or design_id).strip(),
                    "quantity": quantity,
                    "rate": rate,
                    "unit": (row["unit"] or "piece").strip(),
                }
            )
    return rows


def load_tags_csv(known_ids):
    path = CATALOGUE_DIR / "tags.csv"
    if not path.exists():
        return
    loaded = 0
    with open(path, newline="", encoding="utf-8-sig") as f, db.connect() as conn:
        for line_no, row in enumerate(csv.DictReader(f), start=2):
            design_id = (row.get("design_id") or "").strip()
            tags = tagging.clean_tags(row)
            if design_id not in known_ids or tags is None:
                print(f"  ! tags.csv line {line_no}: unknown design or a value outside config.yaml, skipped")
                continue
            if db.get_tag_source(conn, design_id) != "manual":
                db.save_tags(conn, design_id, tags, "manual")
                loaded += 1
    if loaded:
        print(f"tags.csv: {loaded} designs tagged by staff")


def ingest(retag=False):
    db.init_db()
    rows = read_stock_csv()
    print(f"stock.csv: {len(rows)} valid designs")

    # 1. Designs and stock (stock and rate come ONLY from stock.csv)
    with db.connect() as conn:
        for r in rows:
            db.upsert_design(conn, r["design_id"], r["image_file"], r["name"], r["quantity"], r["rate"], r["unit"])
        gone = db.remove_designs_not_in(conn, {r["design_id"] for r in rows})
    if gone:
        print(f"Removed {len(gone)} designs no longer in stock.csv")

    # 1b. Staff tags from catalogue/tags.csv (optional). They count as checked
    #     by staff; edits made later in the app are never overwritten.
    load_tags_csv({r["design_id"] for r in rows})

    # 2. Work out what still needs doing
    with db.connect() as conn:
        need_embedding = [r for r in rows if db.get_embedding_file(conn, r["design_id"]) != r["image_file"]]
        need_tags = []
        for r in rows:
            source = db.get_tag_source(conn, r["design_id"])
            if source is None or (retag and source != "manual"):
                need_tags.append(r)

    if not need_embedding and not need_tags:
        print("Everything is up to date.")
        return

    # 3. CLIP embeddings for new or changed photos
    if need_embedding:
        print(f"Computing image embeddings for {len(need_embedding)} photos...")
        for r in need_embedding:
            img = load_image_file(CATALOGUE_DIR / r["image_file"])  # already checked readable
            vector = embeddings.encode_images([img])[0]
            with db.connect() as conn:
                db.save_embedding(conn, r["design_id"], r["image_file"], vector)

    # 4. Tags: Gemini first, CLIP if Gemini is off or failing
    provider = llm.get_llm()
    print(f"Tagging {len(need_tags)} designs (LLM: {provider.name})...")
    ids, matrix = db.load_embeddings()
    vector_by_id = dict(zip(ids, matrix, strict=True))
    pause = CONFIG["llm"].get("seconds_between_calls", 0)
    failures_in_a_row = 0
    counts = {"gemini": 0, "clip": 0}

    for r in need_tags:
        vector = vector_by_id[r["design_id"]]
        img = load_image_file(CATALOGUE_DIR / r["image_file"])

        if provider.available and failures_in_a_row < 3:
            tags, source = tagging.tag_image(img, vector)
            failures_in_a_row = failures_in_a_row + 1 if source == "clip" else 0
            if failures_in_a_row == 3:
                print(f"  ! Gemini failed 3 times in a row ({provider.last_error}). Using CLIP for the rest.")
            time.sleep(pause)  # stay under the free-tier rate limit
        else:
            tags, source = tagging.tag_with_clip(vector), "clip"

        with db.connect() as conn:
            db.save_tags(conn, r["design_id"], tags, source)
        counts[source] += 1
        print(f"  {r['design_id']}: {source:6s} {tags['main_colour']} {tags['pattern']} {tags['garment_type']}")

    print(f"Done. Tagged by Gemini: {counts['gemini']}, by CLIP fallback: {counts['clip']}.")
    print("Check and correct tags in the app's Catalogue tab.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load catalogue/stock.csv into the database")
    parser.add_argument("--retag", action="store_true", help="re-tag designs (staff-corrected tags are kept)")
    ingest(retag=parser.parse_args().retag)
