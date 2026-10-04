"""Build a sample catalogue so the app can be demoed without a real shop's data.

Two ways to use it:

  1) Download openly licensed photos from Wikimedia Commons:
       python scripts/fetch_sample_catalogue.py --download --count 30

  2) You already put your own photos in catalogue/ and just need a stock.csv:
       python scripts/fetch_sample_catalogue.py --from-folder

Either way it writes catalogue/stock.csv. Stock and rate values are MADE UP
(random but repeatable) because this is sample data. A real shop replaces
stock.csv with its own file.
"""

import argparse
import csv
import random
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "catalogue"
STOCK_CSV = CATALOGUE / "stock.csv"
CREDITS = CATALOGUE / "CREDITS.md"

API = "https://commons.wikimedia.org/w/api.php"
# Wikimedia asks every script to identify itself.
HEADERS = {"User-Agent": "SwatchMatchHackathon/0.1 (sample data fetcher; educational use)"}

# Categories we try, in order. Missing categories are simply skipped.
CATEGORIES = [
    "Sarees",
    "Saris",
    "Bandhani",
    "Patola",
    "Banarasi sari",
    "Kanchipuram sari",
    "Ikat textiles",
    "Leheriya",
    "Block printed textiles of India",
]

# Only licences that allow reuse with attribution.
OK_LICENCES = ("cc0", "public domain", "cc by", "cc-by", "pd")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def clean_html(text):
    """Commons metadata often contains HTML; strip tags for the credits file."""
    return re.sub(r"<[^>]+>", "", text or "").strip()


def fetch_category(category, limit):
    """Return a list of dicts (title, thumb_url, licence, artist, page_url) for one category."""
    params = {
        "action": "query",
        "format": "json",
        "generator": "categorymembers",
        "gcmtitle": f"Category:{category}",
        "gcmtype": "file",
        "gcmlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime",
        "iiurlwidth": 640,
    }
    resp = requests.get(API, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    pages = resp.json().get("query", {}).get("pages", {})

    items = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        if info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        meta = info.get("extmetadata", {})
        licence = clean_html(meta.get("LicenseShortName", {}).get("value", ""))
        if not licence.lower().startswith(OK_LICENCES):
            continue
        items.append(
            {
                "title": page["title"],
                "thumb_url": info.get("thumburl") or info.get("url"),
                "licence": licence,
                "artist": clean_html(meta.get("Artist", {}).get("value", "")) or "Unknown",
                "page_url": info.get("descriptionurl", ""),
            }
        )
    return items


def name_from_title(title):
    """'File:Red bandhani saree 2.jpg' -> 'Red Bandhani Saree 2'."""
    name = Path(title.replace("File:", "")).stem
    name = re.sub(r"[_\-]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:60].title() or "Untitled design"


def download(count):
    CATALOGUE.mkdir(exist_ok=True)
    seen, chosen = set(), []
    for cat in CATEGORIES:
        if len(chosen) >= count:
            break
        try:
            items = fetch_category(cat, limit=50)
        except requests.RequestException as e:
            print(f"  ! could not read category {cat}: {e}")
            continue
        print(f"  {cat}: {len(items)} usable images")
        for item in items:
            if item["title"] not in seen and len(chosen) < count:
                seen.add(item["title"])
                chosen.append(item)

    if not chosen:
        sys.exit("No images downloaded. Is commons.wikimedia.org reachable? "
                 "Otherwise add photos to catalogue/ and use --from-folder.")

    rows, credits = [], []
    for i, item in enumerate(chosen, start=1):
        design_id = f"D{i:03d}"
        filename = f"{design_id}.jpg"
        try:
            img = requests.get(item["thumb_url"], headers=HEADERS, timeout=60)
            img.raise_for_status()
        except requests.RequestException as e:
            print(f"  ! skip {item['title']}: {e}")
            continue
        (CATALOGUE / filename).write_bytes(img.content)
        rows.append((design_id, filename, name_from_title(item["title"])))
        credits.append(
            f"| {design_id} | [{item['title']}]({item['page_url']}) | {item['artist']} | {item['licence']} |"
        )
        print(f"  saved {filename}")

    write_stock_csv(rows)
    CREDITS.write_text(
        "# Image credits\n\n"
        "Sample images from Wikimedia Commons, resized to 640 px wide. "
        "Stock and rate values in stock.csv are made up for the demo.\n\n"
        "| Design | Source | Author | Licence |\n|---|---|---|---|\n"
        + "\n".join(credits)
        + "\n",
        encoding="utf-8",
    )
    print(f"Done: {len(rows)} designs. Credits in {CREDITS.relative_to(ROOT)}")


def from_folder():
    files = sorted(p for p in CATALOGUE.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if not files:
        sys.exit("No images found in catalogue/. Add .jpg/.png/.webp files first.")
    rows = []
    for i, path in enumerate(files, start=1):
        rows.append((f"D{i:03d}", path.name, name_from_title(path.name)))
    write_stock_csv(rows)
    print(f"Done: {len(rows)} designs from your own photos.")


def write_stock_csv(rows):
    """rows = [(design_id, image_file, name)]. Adds made-up but repeatable stock and rate."""
    rng = random.Random(42)
    with open(STOCK_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["design_id", "image_file", "name", "quantity_available", "rate", "unit"])
        for design_id, image_file, name in rows:
            quantity = rng.choice([0, 3, 5, 8, 12, 20, 35, 50])
            rate = rng.randrange(600, 4500, 50)
            writer.writerow([design_id, image_file, name, quantity, rate, "piece"])
    print(f"Wrote {STOCK_CSV.relative_to(ROOT)} (stock and rate are sample values)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--download", action="store_true", help="download sample photos from Wikimedia Commons")
    group.add_argument("--from-folder", action="store_true", help="write stock.csv for photos already in catalogue/")
    parser.add_argument("--count", type=int, default=30, help="how many photos to download")
    args = parser.parse_args()
    if args.download:
        download(args.count)
    else:
        from_folder()
