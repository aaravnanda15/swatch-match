"""Make test query photos for evaluate.py from catalogue photos.

    python scripts/make_test_queries.py

Real buyers send phone photos: cropped, tilted, different light, compressed by
WhatsApp. This imitates that (crop, rotate, brightness, colour cast, blur,
low JPEG quality) so the query files are never identical to catalogue files.
It is still EASIER than real buyer photos, which is why the README reports
the number as "sample data, augmented queries". Real phone photos of real
stock give the honest number.

Writes test_queries/*.jpg and the photo rows of test_queries.csv. The text
rows (written by hand) are kept.
"""

import csv
import random
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "catalogue"
OUT = ROOT / "test_queries"
CSV_FILE = ROOT / "test_queries.csv"

# Designs to photograph, and (design, words) pairs for photo + text queries
PHOTO_ONLY = ["D002", "D003", "D005", "D007", "D009", "D012", "D014", "D016",
              "D019", "D020", "D022", "D023", "D026", "D028", "D030"]
PHOTO_AND_TEXT = [("D010", "isme blue wala silk chahiye"), ("D024", "same orange dupatta")]


def buyer_style(img, rng):
    img = ImageOps.exif_transpose(img).convert("RGB")
    w, h = img.size
    keep = rng.uniform(0.6, 0.85)
    left, top = rng.uniform(0, 1 - keep) * w, rng.uniform(0, 1 - keep) * h
    img = img.crop((int(left), int(top), int(left + keep * w), int(top + keep * h)))
    img = img.rotate(rng.uniform(-10, 10), expand=False, fillcolor=(235, 235, 230))
    img = ImageEnhance.Brightness(img).enhance(rng.uniform(0.75, 1.2))
    img = ImageEnhance.Color(img).enhance(rng.uniform(0.85, 1.15))
    # Slight warm or cool cast, like indoor shop lighting
    r, g, b = img.split()
    cast = rng.uniform(-12, 12)
    r = r.point(lambda v: max(0, min(255, v + cast)))
    b = b.point(lambda v: max(0, min(255, v - cast)))
    img = Image.merge("RGB", (r, g, b)).filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 1.0)))
    img.thumbnail((640, 640))
    return img


def main():
    rng = random.Random(7)
    OUT.mkdir(exist_ok=True)
    rows = []
    for design_id in PHOTO_ONLY:
        rows.append(make_photo(design_id, "", rng))
    for design_id, text in PHOTO_AND_TEXT:
        rows.append(make_photo(design_id, text, rng))

    # Keep the hand-written text-only rows already in the CSV
    text_rows = []
    if CSV_FILE.exists():
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            text_rows = [r for r in csv.DictReader(f) if not r["query_image"]]

    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["query_image", "query_text", "expected_design_id"])
        writer.writeheader()
        writer.writerows(rows + text_rows)
    print(f"Wrote {len(rows)} photo queries to {OUT.name}/ and kept {len(text_rows)} text queries.")


def make_photo(design_id, text, rng):
    source = CATALOGUE / f"{design_id}.jpg"
    name = f"q_{design_id}{'_text' if text else ''}.jpg"
    buyer_style(Image.open(source), rng).save(OUT / name, quality=rng.randint(50, 70))
    return {"query_image": name, "query_text": text, "expected_design_id": design_id}


if __name__ == "__main__":
    main()
