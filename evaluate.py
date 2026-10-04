"""How often does the right design come up? Run:

    python evaluate.py            summary
    python evaluate.py --show     plus one line per query

Reads test_queries.csv (query_image, query_text, expected_design_id). The
expected id may list several acceptable designs: "D020|D022".

Honesty rules:
  * Refuses to run if a query photo is byte-identical to a catalogue photo
    (that would test nothing).
  * Prints counts, not just percentages, and whether the AI was used or the
    run was in fallback mode.
  * With the sample data, query photos are edited copies of catalogue photos
    (see scripts/make_test_queries.py). Real buyer phone photos are harder.
"""

import argparse
import csv
import hashlib
import sys
import time
from collections import defaultdict
from pathlib import Path

from backend import llm
from backend.agent import orchestrator
from backend.config import CATALOGUE_DIR, CONFIG
from backend.images import load_image_file

ROOT = Path(__file__).resolve().parent
QUERIES_CSV = ROOT / "test_queries.csv"
QUERIES_DIR = ROOT / "test_queries"


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_not_copies(rows):
    catalogue = {file_hash(p): p.name for p in CATALOGUE_DIR.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")}
    for row in rows:
        if row["query_image"]:
            h = file_hash(QUERIES_DIR / row["query_image"])
            if h in catalogue:
                sys.exit(f"REFUSING: {row['query_image']} is identical to catalogue/{catalogue[h]}. "
                         "Use a different photo of the design.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", action="store_true", help="print every query")
    args = parser.parse_args()

    with open(QUERIES_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    check_not_copies(rows)

    hits1, hits5, totals = defaultdict(int), defaultdict(int), defaultdict(int)
    right_scores, wrong_scores = [], []
    labels_when_right = defaultdict(int)
    fallback_runs = 0
    provider = llm.get_llm()
    # Stay under the free Gemini rate limit (each query makes 1-2 calls)
    pause = CONFIG["llm"].get("seconds_between_calls", 0) if provider.available else 0

    for row in rows:
        time.sleep(pause)
        img = load_image_file(QUERIES_DIR / row["query_image"]) if row["query_image"] else None
        expected = set(row["expected_design_id"].split("|"))
        answer = orchestrator.handle_enquiry(row["query_text"], img)
        fallback_runs += answer["fallback_mode"]
        ids = [r["design_id"] for r in answer["results"]]
        kind = answer["mode"]

        totals[kind] += 1
        top1 = bool(ids) and ids[0] in expected
        top5 = bool(expected & set(ids[:5]))
        hits1[kind] += top1
        hits5[kind] += top5
        if ids:
            (right_scores if top1 else wrong_scores).append(answer["results"][0]["score"])
            if top1:
                labels_when_right[answer["results"][0]["label_text"]] += 1

        if args.show:
            query = row["query_image"] or ""
            if row["query_text"]:
                query += f' "{row["query_text"]}"'
            mark = "TOP1" if top1 else ("top5" if top5 else "MISS")
            first = f"{ids[0]} {answer['results'][0]['score']:.2f}" if ids else "-"
            print(f"  {mark:4s}  {query.strip():45s} want {row['expected_design_id']:15s} got {first}")

    print("\nSwatch Match evaluation (sample data, augmented queries)")
    print(f"  AI: {provider.name}, model {CONFIG['llm']['model'] if provider.available else '-'}; "
          f"{fallback_runs} of {len(rows)} queries ran in fallback mode")
    print(f"  {'enquiry type':16s} {'top-1':>10s} {'top-5':>10s}")
    for kind in sorted(totals):
        print(f"  {kind:16s} {hits1[kind]:>4d}/{totals[kind]:<5d} {hits5[kind]:>4d}/{totals[kind]:<5d}")
    n = sum(totals.values())
    t1, t5 = sum(hits1.values()), sum(hits5.values())
    print(f"  {'ALL':16s} {t1:>4d}/{n:<5d} {t5:>4d}/{n:<5d}   (top-1 {t1 / n:.0%}, top-5 {t5 / n:.0%})")

    if right_scores:
        print(f"\n  Score of the first result when it was right: min {min(right_scores):.2f}, "
              f"median {sorted(right_scores)[len(right_scores) // 2]:.2f}")
    if wrong_scores:
        print(f"  Score of the first result when it was wrong: max {max(wrong_scores):.2f}, "
              f"median {sorted(wrong_scores)[len(wrong_scores) // 2]:.2f}")
    if labels_when_right:
        print("  Labels shown when right: " + ", ".join(f"{k} {v}" for k, v in labels_when_right.items()))


if __name__ == "__main__":
    main()
