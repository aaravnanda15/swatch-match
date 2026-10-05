"""Five scripted WhatsApp chats: the reply before the AI wrote replies vs the reply now.

    python scripts/demo_conversations.py          # before vs after, also saved to docs/demo_conversations.md
    python scripts/demo_conversations.py --json   # only this code's replies, as JSON

"Before" runs the same chats on commit 5a7f844 in a temporary git worktree.
Both runs use a copy of the database, so the real one is never touched.
Needs GEMINI_API_KEY in .env; takes a few minutes (Gemini calls are spaced out).
"""

import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BEFORE = "5a7f844"  # the last commit before the AI wrote replies

CHATS = {
    "Ramesh Textiles (Hinglish wedding order)": ["laal bandhani saree chahiye shaadi ke liye", "30 piece", "haan"],
    "Patel Fabrics (Gujarati, unit mix-up)": ["લાલ ઇકત કાપડ જોઈએ છે", "૨૦ કિલો", "હા"],
    "Anita (delivery and COD)": ["blue dupatta", "delivery to Surat?", "COD?", "10 pcs"],
    "Kavita Boutique (turns down two designs)": ["red saree?", "not this one, show another", "no, another one",
                                                "the first one"],
    "Sunil Traders (rude, then a real question)": ["yo bro", "wtf", "ok sorry, is it pure silk?"],
}


def play():
    tmp = Path(tempfile.mkdtemp(prefix="swatch-demo-"))
    shutil.copy(ROOT / "data" / "swatch.db", tmp / "swatch.db")
    os.environ["SWATCH_DB"] = str(tmp / "swatch.db")  # before backend is imported
    sys.path.insert(0, str(ROOT))
    from backend import conversation, db, inbox, llm

    db.init_db()
    provider = llm.get_llm()
    if provider.available:  # stay under the free tier's calls per minute
        real, last = provider._generate_once, [0.0]

        def paced(*args, **kwargs):
            time.sleep(max(0.0, 4.6 - (time.time() - last[0])))
            last[0] = time.time()
            return real(*args, **kwargs)

        provider._generate_once = paced

    replies = {}
    for title, messages in CHATS.items():
        name, phone = title.split(" (")[0], "9100" + str(random.randint(10**7, 10**8 - 1))
        replies[title] = []
        for text in messages:
            inbox.handle_message({"id": f"wamid.CHAT{time.time_ns()}", "phone": phone, "name": name,
                                  "timestamp": int(time.time()), "type": "text", "original_type": "text",
                                  "text": text, "media_id": None})
            state = conversation.get_state(phone)
            replies[title].append([text, state.get("last_reply", ""), state.get("reply_source")])
    return replies


def play_before():
    tree = Path(tempfile.mkdtemp(prefix="swatch-before-")) / "repo"
    subprocess.run(["git", "worktree", "add", "--detach", str(tree), BEFORE], cwd=ROOT, check=True, capture_output=True)
    try:
        (tree / "data").mkdir(exist_ok=True)
        for name in (".env", "data/models", "data/swatch.db"):
            if (ROOT / name).exists():
                (tree / name).symlink_to(ROOT / name)
        shutil.copy(__file__, tree / "scripts" / "demo_conversations.py")
        run = subprocess.run([sys.executable, "scripts/demo_conversations.py", "--json"], cwd=tree,
                             capture_output=True, text=True, check=True)
        return json.loads(run.stdout.strip().splitlines()[-1])
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(tree)], cwd=ROOT, capture_output=True)


def who_wrote(source, reply):
    if source:
        return {"composed": "AI, checked", "template": "template"}[source]
    return "template, can wait" if reply else "no reply needed"


def cell(text):
    return (text or "_(no reply, kept away from the seller)_").replace("|", "/").replace("\n", "<br>")


def main():
    if "--json" in sys.argv:
        print(json.dumps(play(), ensure_ascii=False))
        return
    print(f"Running the chats on {BEFORE} (before)...", flush=True)
    before = play_before()
    print("Running the chats on this code (after)...", flush=True)
    after = play()

    lines = ["# Before and after: the same five chats", "",
             f"Before = commit {BEFORE} (fixed templates). After = this code (the AI writes the reply, "
             "checked against stock.csv). Made by `scripts/demo_conversations.py`.", ""]
    for title, turns in after.items():
        print(f"\n=== {title}")
        lines += [f"## {title}", "", "| Buyer | Before | After |", "|---|---|---|"]
        for (text, old, _), (_, new, source) in zip(before[title], turns, strict=True):
            print(f"\nBUYER:  {text}\nBEFORE: {old or '(no reply)'}\nAFTER ({who_wrote(source, new)}): {new or '(no reply)'}")
            lines.append(f"| {cell(text)} | {cell(old)} | {cell(new)}<br>_{who_wrote(source, new)}_ |")
        lines.append("")
    (ROOT / "docs" / "demo_conversations.md").write_text("\n".join(lines), encoding="utf-8")
    print("\nSaved docs/demo_conversations.md")


if __name__ == "__main__":
    main()
