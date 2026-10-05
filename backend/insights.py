"""Numbers for the Insights tab, worked out from enquiries and approved replies."""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median

from backend import db

GOOD = ("very_close", "similar")
DESCRIBE_ORDER = ("main_colour", "fabric", "pattern", "work_type", "garment_type")
EMPTY = ("none", "other", "unknown", "plain")


def _parse(sqlite_time):
    return datetime.strptime(sqlite_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def _describe(attributes):
    words = [attributes[a] for a in DESCRIBE_ORDER if attributes.get(a) and attributes[a] not in EMPTY]
    return " ".join(words)


def compute(days=7, tz_offset_minutes=330):
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    rows, offered_lists = db.insight_rows(since.strftime("%Y-%m-%d %H:%M:%S"))
    local = timedelta(minutes=tz_offset_minutes)

    total = len(rows)
    on_whatsapp = sum(1 for r in rows if r["source"] == "whatsapp")
    replied = [r for r in rows if r["replied_at"]]
    reply_minutes = [
        max(0.0, (_parse(r["replied_at"]) - _parse(r["created_at"])).total_seconds() / 60) for r in replied
    ]
    matchable = [r for r in rows if r["answer"] and r["mode"] not in ("vague", "unsupported")]
    good = [r for r in matchable if r["answer"]["results"] and r["answer"]["results"][0]["label"] in GOOD]

    today = (now + local).date()
    per_day = {today - timedelta(days=i): 0 for i in range(days - 1, -1, -1)}
    for r in rows:
        day = (_parse(r["created_at"]) + local).date()
        if day in per_day:
            per_day[day] += 1

    asked = {"main_colour": Counter(), "pattern": Counter(), "garment_type": Counter()}
    languages = Counter()
    for r in rows:
        answer = r["answer"]
        if not answer:
            continue
        for attr, counter in asked.items():
            value = answer["query"]["attributes"].get(attr)
            if value and value not in EMPTY:
                counter[value] += 1
        if r["mode"] in ("text_only", "image_and_text", "vague"):
            languages[answer["query"].get("language") or "en"] += 1

    # missed demand: requests nothing in stock fully matched
    missed = defaultdict(lambda: {"count": 0, "budgets": []})
    for r in matchable:
        answer = r["answer"]
        attributes = answer["query"]["attributes"]
        results = answer["results"]
        # Served only if something in stock matched everything asked ("Very close")
        served = any(x["label"] == "very_close" and x["in_stock"] for x in results)
        wanted = _describe(attributes)
        if not served and wanted:
            missed[wanted]["count"] += 1
            if answer["query"].get("max_rate"):
                missed[wanted]["budgets"].append(answer["query"]["max_rate"])
    missed_list = [
        {"request": k, "count": v["count"], "budget": min(v["budgets"]) if v["budgets"] else None}
        for k, v in sorted(missed.items(), key=lambda kv: -kv[1]["count"])
    ][:6]

    # ...and designs that were a good match but out of stock
    out_of_stock = Counter()
    for r in matchable:
        for x in r["answer"]["results"]:
            if x["label"] in GOOD and not x["in_stock"]:
                out_of_stock[x["design_id"]] += 1

    offered = Counter(d for picks in offered_lists for d in picks)

    def design_list(counter, n):
        out = []
        for design_id, count in counter.most_common(n):
            d = db.get_design(design_id)
            if d:
                out.append({"design_id": design_id, "name": d["name"], "image_file": d["image_file"],
                            "count": count, "quantity_available": d["quantity_available"]})
        return out

    return {
        "days": days,
        "total": total,
        "on_whatsapp": on_whatsapp,
        "replied": len(replied),
        "reply_rate": round(len(replied) / total, 3) if total else None,
        "median_reply_minutes": round(median(reply_minutes), 1) if reply_minutes else None,
        "good_match_rate": round(len(good) / len(matchable), 3) if matchable else None,
        "matchable": len(matchable),
        "per_day": [{"date": d.isoformat(), "count": c} for d, c in per_day.items()],
        "asked": {k: c.most_common(6) for k, c in asked.items()},
        "languages": languages.most_common(),
        "missed_requests": missed_list,
        "out_of_stock_wanted": design_list(out_of_stock, 5),
        "most_offered": design_list(offered, 5),
        "sample_count": db.count_samples(),
    }
