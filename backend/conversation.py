"""A WhatsApp chat with one buyer, turn by turn.

The app keeps the state of each chat (table `conversations`) and decides every
next step; replies come from agent/templates.py with stock and rate read from
the database. Gemini, when there is a key, only labels the newest message and
pulls out fields (llm.classify_turn) - and it always gets the state, the
pending question and the last 6 messages, never the new message alone.
A keyword classifier does the same job without Gemini.
"""

import json
import re
from datetime import datetime, timedelta, timezone

from backend import db, enquiries, llm
from backend.agent import lexicon, templates
from backend.config import ATTRIBUTES, CONFIG

INTENTS = ("answer_to_question", "new_or_changed_request", "question_about_shown_designs",
           "greeting", "off_topic", "abusive_or_nonsense")
ENQUIRY_FIELDS = ("garment_type", "main_colour", "secondary_colour", "pattern", "border", "fabric", "work_type")
OFF_TOPIC_LIMIT = 3
MERGE_SECONDS = CONFIG["whatsapp"]["merge_seconds"]

SWEAR = {"shit", "fuck", "fucking", "fck", "damn", "bitch", "bastard", "asshole", "crap", "wtf", "stfu",
         "bc", "mc", "bsdk", "bkl", "chutiya", "chutiye", "madarchod", "behenchod", "saala", "sala", "kutta",
         "kamina", "harami", "gandu", "idiot", "stupid", "dumb"}
SLANG = {"yo", "bro", "bruh", "dude", "lol", "lmao", "rofl", "sup", "yolo", "bae", "fam", "lit", "meh"}
GREETINGS = {"hi", "hello", "hey", "hii", "hiii", "namaste", "namaskar", "good", "morning", "evening", "afternoon",
             "kem", "cho", "salaam", "ram", "jai", "shree", "krishna", "नमस्ते", "नमस्कार", "નમસ્તે", "ji"}
YES = {"yes", "y", "yeah", "yep", "haan", "han", "ha", "haa", "ji", "ok", "okay", "sure", "done", "confirm", "theek",
       "thik", "chalega", "kar", "do", "those", "le", "lenge", "हाँ", "हां", "जी", "ठीक", "હા", "બરાબર"}
NO = {"no", "nope", "nahi", "nahin", "na", "mat", "नहीं", "ना", "ના", "નહીં"}
FILLER = {"chahiye", "chahie", "chaiye", "please", "pls", "only", "total", "de", "do", "bhejo", "need", "want", "i",
          "we", "ji", "ok", "of", "the", "it", "them", "sir", "bhai", "chahiye.", "चाहिए", "જોઈએ", "joie", "joiye"}
# Messages that only cost the seller time: acknowledgements, spam, things the shop doesn't sell
ACK = {"ok", "okay", "okk", "k", "kk", "hmm", "hmmm", "hm", "acha", "achha", "accha", "oh", "ohh", "thanks", "thank",
       "you", "thx", "ty", "nice", "cool", "fine", "alright", "hehe", "haha", "zzz"}
SPAM = re.compile(r"https?://|www\.|\bclick\b|\bearn\b|lottery|\bloan\b|crypto|bitcoin|investment|\bprize\b|"
                  r"subscribe|\botp\b|forwarded|work from home|\bwon\b", re.IGNORECASE)
NOT_SOLD = {"shoe", "shoes", "sandal", "sandals", "chappal", "phone", "mobile", "laptop", "car", "bike", "pizza", "food",
            "watch", "jewellery", "jewelry", "furniture", "tv", "electronics", "medicine", "jeans", "tshirt"}
STOCK_QUESTION = re.compile(r"how many|in stock|available|\bstock\b|\bprice\b|\brate\b|kitn[aei]|kya rate|"
                            r"कितन|स्टॉक|कीमत|કેટલા|સ્ટોક|ભાવ", re.IGNORECASE)
SIMILAR = re.compile(r"similar|other|more designs|aur dikha|dusr|milte|और|બીજી|મળતી", re.IGNORECASE)
UNITS = {
    "piece": {"pc", "pcs", "piece", "pieces", "nos", "no", "nag", "पीस", "नग", "પીસ", "નંગ",
              "saree", "sarees", "sari", "saris", "dupatta", "dupattas"},
    "metre": {"m", "mtr", "mtrs", "meter", "meters", "metre", "metres", "मीटर", "મીટર"},
    "kg": {"kg", "kgs", "kilo", "kilos", "kilogram", "kilograms", "g", "gm", "gms", "gram", "grams", "किलो", "કિલો"},
    "yard": {"yard", "yards", "yd", "gaj", "गज"},
    "set": {"set", "sets"},
    "dozen": {"dozen", "dozens", "darjan", "दर्जन"},
}
WORD = re.compile(r"[a-z]+|[ऀ-ॿ]+|[઀-૿]+")


def new_state():
    return {
        "enquiry": {}, "budget": None, "shortlist": [], "focus": None, "photo_file": None,
        "quantity": None, "unit": None, "pending_question": None, "stage": "browsing",
        "off_topic_count": 0, "flagged": False, "language": "en", "summary": "",
        "enquiry_id": None, "turns": 0, "last_intent": None, "last_reply": "",
        "last_buyer_text": "", "filtered_count": 0,
    }


def get_state(phone):
    return db.get_conversation(phone) or new_state()


def unit_of(word):
    if not word:
        return None
    word = word.strip(".").lower()
    return next((unit for unit, words in UNITS.items() if word in words), word)


# ---------- reading the message ----------

def keyword_classify(state, text):
    """(intent, fields, sure). `sure` = no need to ask Gemini."""
    low = lexicon.translate_digits(text.lower().strip())
    words = WORD.findall(low)
    expects = (state["pending_question"] or {}).get("expects")
    fields = {}

    if SPAM.search(low):
        return "off_topic", {"filter": "spam"}, True
    if not re.search(r"[a-z0-9ऀ-ॿ઀-૿]", low):
        return "abusive_or_nonsense", {"filter": "noise"}, True  # emojis or symbols only
    if any(w in SWEAR or w in SLANG for w in words):
        return "abusive_or_nonsense", {"filter": "rude"}, True

    number = re.search(r"\d+(?:\.\d+)?", low)
    if number and expects in ("quantity", "confirm_quantity", "take_available"):
        rest = WORD.findall(low[number.end():]) + WORD.findall(low[:number.start()])
        unit = next((w for w in rest if unit_of(w) in UNITS), None)
        if all(w in FILLER or unit_of(w) in UNITS for w in rest):
            fields.update(quantity=float(number.group()), unit=unit)
            return "answer_to_question", fields, True

    if any(w in NOT_SOLD for w in words) and not lexicon.parse(text)["attributes"]:
        return "off_topic", {"filter": "not_sold"}, True
    if expects in ("confirm_quantity", "confirm_order", "take_available"):
        if expects == "take_available" and SIMILAR.search(low):
            return "answer_to_question", {"choice": "similar"}, True
        if words and set(words) & YES and not set(words) & NO:
            return "answer_to_question", {"choice": "yes"}, True
        if words and set(words) & NO:
            return "answer_to_question", {"choice": "no"}, True

    if words and all(w in ACK for w in words):
        return "off_topic", {"filter": "noise"}, True
    parsed = lexicon.parse(text)
    if parsed["attributes"] or parsed["max_rate"]:
        fields.update(attributes=parsed["attributes"], budget=parsed["max_rate"])
        if state["shortlist"] and STOCK_QUESTION.search(low) and not parsed["attributes"]:
            return "question_about_shown_designs", {}, True
        return "new_or_changed_request", fields, False
    if state["shortlist"] and STOCK_QUESTION.search(low):
        return "question_about_shown_designs", fields, True
    if words and all(w in GREETINGS for w in words):
        return "greeting", fields, True
    return "off_topic", fields, False


def gemini_classify(state, text, history):
    provider = llm.get_llm()
    if not provider.available:
        return None
    pending = (state["pending_question"] or {}).get("text")
    lines = [f"{'buyer' if m['direction'] == 'in' else 'shop'}: {m['text'] or '[photo]'}" for m in history]
    answer = provider.classify_turn(json.dumps(_state_for_llm(state), ensure_ascii=False), pending,
                                    "\n".join(lines), text)
    if not isinstance(answer, dict) or answer.get("intent") not in INTENTS:
        return None
    attributes = {}
    raw = answer.get("attributes")
    for attr, value in (raw if isinstance(raw, dict) else {}).items():
        value = str(value).strip().lower()
        if attr in ATTRIBUTES and value in ATTRIBUTES[attr]:
            attributes[attr] = value
    fields = {"attributes": attributes, "budget": _positive(answer.get("budget")),
              "quantity": _positive(answer.get("quantity")),
              "unit": str(answer["unit"]) if answer.get("unit") else None}
    if answer.get("language") in templates.TURN:
        fields["language"] = answer["language"]
    return answer["intent"], fields


def _state_for_llm(state):
    """The state without the bookkeeping, small enough for every call."""
    keep = ("enquiry", "budget", "shortlist", "quantity", "unit", "stage", "summary")
    return {k: state[k] for k in keep}


def _positive(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def classify(state, text, history):
    intent, fields, sure = keyword_classify(state, text)
    if sure:
        return intent, fields, "keywords"
    gemini = gemini_classify(state, text, history)
    if gemini is None:
        return intent, fields, "keywords"
    g_intent, g_fields = gemini
    # Gemini can't turn a reply into an answer when nothing was asked
    if g_intent == "answer_to_question" and not state["pending_question"]:
        g_intent = "off_topic"
    if g_intent == "new_or_changed_request" and not (g_fields["attributes"] or g_fields["budget"]):
        g_fields["attributes"], g_fields["budget"] = fields.get("attributes", {}), fields.get("budget")
    return g_intent, g_fields, "gemini"


# ---------- deciding the reply ----------

def handle_turn(phone, name, text, img=None, image_file=None, buyer=None):
    state = get_state(phone)
    state["turns"] += 1
    history = db.recent_chat(phone, 7)[:-1]  # the newest message is already stored

    normalized = " ".join(text.lower().split())
    if img is not None:
        intent, fields, read_by = "new_or_changed_request", {}, "photo"
    elif normalized and normalized == state.get("last_buyer_text"):
        intent, fields, read_by = "off_topic", {"filter": "duplicate"}, "keywords"
    else:
        intent, fields, read_by = classify(state, text, history)
    if text:
        state["last_buyer_text"] = normalized

    lang = state["language"]
    if intent == "new_or_changed_request" and text:
        detected = fields.get("language") or lexicon.detect_language(text)
        if len(WORD.findall(text.lower())) > 1 or state["turns"] == 1:
            lang = state["language"] = detected

    # needs_reply: shown to the seller as New. low: reply drafted, but it can wait.
    # filtered: nothing worth the seller's time (no reply, not shown as New).
    priority = "needs_reply"
    if intent == "new_or_changed_request":
        reply = _new_request(state, phone, text, img, image_file, buyer, fields)
    elif intent == "answer_to_question":
        reply = _answer(state, fields)
    elif intent == "question_about_shown_designs":
        reply = _stock_lines(state)
    elif intent == "greeting":
        reply = _join(templates.turn_text(lang, "greeting"), _pending_or_details(state, short=True))
        priority = "low"
    else:
        reply, priority = _off_topic(state, fields.get("filter"))

    if priority == "needs_reply":
        state["off_topic_count"] = 0
        state["flagged"] = False  # a real message un-mutes the chat
    if priority == "filtered":
        state["filtered_count"] += 1
    state["last_intent"] = intent
    state["last_reply"] = reply
    state["last_priority"] = priority
    state["summary"] = _summary(state)
    db.save_conversation(phone, state)

    # filtered messages leave the enquiry exactly as the seller last saw it
    if intent != "new_or_changed_request" and state["enquiry_id"] and priority != "filtered":
        db.set_followup(state["enquiry_id"], {
            "buyer_text": text, "intent": intent, "reply": reply, "read_by": read_by, "priority": priority,
            "filter": fields.get("filter"), "flagged": state["flagged"], "stage": state["stage"],
            "summary": state["summary"],
        }, surface=priority == "needs_reply")
    return {"intent": intent, "reply": reply, "read_by": read_by, "priority": priority, "state": state}


def _new_request(state, phone, text, img, image_file, buyer, fields):
    for attr, value in (fields.get("attributes") or {}).items():
        state["enquiry"][attr] = value
    if fields.get("budget"):
        state["budget"] = fields["budget"]
    if img is not None:
        state["photo_file"] = image_file

    answer = _merge_with_recent(phone, text, img, image_file)
    if answer is None:
        if img is None and state["photo_file"] and state["enquiry"]:
            # a change to an earlier photo enquiry ("actually blue"): keep the photo
            img, image_file = enquiries.load_upload(state["photo_file"]), state["photo_file"]
        query_text = text if img is not None else _compose(state) or text
        answer = enquiries.run(query_text, img, image_file, whatsapp=buyer, display_text=text)
    adopt_answer(state, answer)
    lang = state["language"]

    if answer["clarifying_question"]:
        state["pending_question"] = {"text": answer["clarifying_question"], "expects": "details"}
        state["stage"] = "browsing"
        return answer["clarifying_question"]
    picks = _good_picks(answer)
    if not picks:
        state["pending_question"] = {"text": templates.turn_text(lang, "ask_details"), "expects": "details"}
        return _join(templates.turn_text(lang, "no_more"), state["pending_question"]["text"])
    item, _, _ = templates.item_words(lang, state["enquiry"])
    state["pending_question"] = {"text": templates.turn_text(lang, "ask_quantity", item=item), "expects": "quantity"}
    state["stage"] = "asked_quantity"
    state["quantity"] = state["unit"] = None
    return templates.draft_reply(lang, [db.get_design(d) for d in picks], no_match=answer["no_match"])


def _merge_with_recent(phone, text, img, image_file):
    """A photo and a text sent a moment apart are one enquiry."""
    since = (datetime.now(timezone.utc) - timedelta(seconds=MERGE_SECONDS)).strftime("%Y-%m-%d %H:%M:%S")
    previous = db.find_open_enquiry(phone, since)
    if not previous or previous["mode"] == "unsupported":
        return None
    if img is None and previous["image_file"] and not previous["text"]:
        photo = enquiries.load_upload(previous["image_file"])
        return enquiries.rerun(previous["id"], text, photo, previous["image_file"])
    if img is not None and not previous["image_file"] and previous["text"]:
        return enquiries.rerun(previous["id"], f"{previous['text']} {text}".strip(), img, image_file)
    return None


def adopt_answer(state, answer):
    state["enquiry_id"] = answer["enquiry_id"]
    for attr, value in answer["query"]["attributes"].items():
        state["enquiry"][attr] = value
    if answer["query"]["max_rate"]:
        state["budget"] = answer["query"]["max_rate"]
    if not state["enquiry"].get("garment_type") and answer.get("photo_tags"):
        state["enquiry"]["garment_type"] = answer["photo_tags"].get("garment_type")
    state["shortlist"] = [r["design_id"] for r in answer["results"]]
    picks = _good_picks(answer)
    state["focus"] = picks[0] if picks else None


def _good_picks(answer):
    if answer["clarifying_question"]:
        return []
    good = [r["design_id"] for r in answer["results"] if r["in_stock"] and r["label"] in ("very_close", "similar")]
    if good:
        return good[:3]
    closest = next((r["design_id"] for r in answer["results"] if r["in_stock"]), None)
    return [closest] if closest else []


def _compose(state):
    e = state["enquiry"]
    words = [e.get(a) for a in ("main_colour", "fabric", "pattern", "work_type", "garment_type")]
    text = " ".join(w for w in words if w and w not in ("none", "other", "unknown"))
    if e.get("border") not in (None, "none", "other"):
        text += f" with {e['border']} border"
    if state["budget"]:
        text += f" under {state['budget']:g}"
    return text.strip()


def _answer(state, fields):
    pending = state["pending_question"] or {}
    expects = pending.get("expects")
    choice = fields.get("choice")

    if fields.get("quantity") and expects in ("quantity", "confirm_quantity", "take_available"):
        return _quantity(state, fields["quantity"], fields.get("unit"))
    if expects == "confirm_quantity":
        if choice == "yes":
            return _stock_check(state, pending["value"])
        return _ask_quantity(state)
    if expects == "confirm_order":
        if choice == "yes":
            return _confirmed(state, pending["value"])
        return _ask_quantity(state)
    if expects == "take_available":
        if choice == "yes" and pending.get("value"):
            return _confirmed(state, pending["value"])
        return _show_similar(state)
    return _pending_or_details(state, short=True)  # nothing to act on: repeat what we're waiting for


def _focus(state):
    return db.get_design(state["focus"]) if state["focus"] else None


def _quantity(state, quantity, unit):
    design = _focus(state)
    if design is None:
        return _ask_details(state)
    n = int(quantity) if float(quantity).is_integer() else quantity
    if unit and unit_of(unit) != unit_of(design["unit"]):
        lang = state["language"]
        item, plural, _ = templates.item_words(lang, state["enquiry"])
        units = _units(lang, design["unit"], n)
        text = templates.turn_text(lang, "unit_mismatch", plural=plural, unit=design["unit"], buyer_unit=unit,
                                   n=n, units=units, item=item)
        short = templates.turn_text(lang, "confirm_short", n=n, units=units, item=item)
        state["pending_question"] = {"text": text, "short": short, "expects": "confirm_quantity", "value": n}
        state["stage"] = "confirming"
        return text
    return _stock_check(state, n)


def _stock_check(state, n):
    design = _focus(state)
    lang = state["language"]
    available = design["quantity_available"]
    values = dict(name=design["name"], design=design["design_id"], available=available, n=n,
                  rate=templates._rupees(design["rate"]), unit=_units(lang, design["unit"], 1),
                  units=_units(lang, design["unit"], available), units_n=_units(lang, design["unit"], n))
    state["quantity"], state["unit"] = n, design["unit"]
    state["stage"] = "confirming"
    if available <= 0:
        text = templates.turn_text(lang, "out", **values)
        state["pending_question"] = {"text": text, "expects": "take_available", "value": None}
    elif n > available:
        text = templates.turn_text(lang, "short", **values)
        state["pending_question"] = {"text": text, "expects": "take_available", "value": available}
    else:
        text = templates.turn_text(lang, "in_stock", **values)
        state["pending_question"] = {"text": text, "expects": "confirm_order", "value": n}
    return text


def _confirmed(state, n):
    design = _focus(state)
    lang = state["language"]
    state["quantity"], state["stage"], state["pending_question"] = n, "done", None
    return templates.turn_text(lang, "confirmed", n=n, units=_units(lang, design["unit"], n),
                               name=design["name"], design=design["design_id"])


def _show_similar(state):
    lang = state["language"]
    others = [d for d in (db.get_design(i) for i in state["shortlist"] if i != state["focus"])
              if d and d["quantity_available"] > 0]
    if not others:
        return _join(templates.turn_text(lang, "no_more"), _ask_details(state))
    state["focus"] = others[0]["design_id"]
    return _join(_stock_lines(state, [d["design_id"] for d in others[:3]], ask=False), _ask_quantity(state))


def _stock_lines(state, design_ids=None, ask=True):
    lang = state["language"]
    designs = [db.get_design(i) for i in (design_ids or state["shortlist"][:3])]
    designs = [d for d in designs if d]
    if not designs:
        return _ask_details(state)
    lines = [templates.turn_text(lang, "stock_intro")]
    for d in designs:
        lines.append(templates.turn_text(lang, "stock_line", design=d["design_id"], name=d["name"],
                                         available=d["quantity_available"], rate=templates._rupees(d["rate"]),
                                         unit=_units(lang, d["unit"], 1),
                                         units=_units(lang, d["unit"], d["quantity_available"])))
    text = "\n".join(lines)
    return f"{text}\n\n{_pending_or_details(state, short=True)}" if ask else text


def _ask_quantity(state):
    item, _, _ = templates.item_words(state["language"], state["enquiry"])
    text = templates.turn_text(state["language"], "ask_quantity", item=item)
    state["pending_question"] = {"text": text, "expects": "quantity"}
    state["stage"] = "asked_quantity"
    return text


def _ask_details(state):
    text = templates.turn_text(state["language"], "ask_details")
    state["pending_question"] = {"text": text, "expects": "details"}
    state["stage"] = "browsing"
    return text


def _pending_or_details(state, short=False):
    """The question we're waiting on (its short form when repeating it)."""
    pending = state["pending_question"]
    if not pending:
        return _ask_details(state)
    return pending.get("short", pending["text"]) if short else pending["text"]


def _off_topic(state, kind=None):
    """(reply, priority). Stay polite, never copy the buyer's tone, never touch the
    enquiry, and keep anything useless away from the seller."""
    lang = state["language"]
    if kind == "duplicate":
        return "", "filtered"  # the reply to the first copy still stands
    if kind in ("noise", "spam"):
        return "", "filtered"  # nothing to answer, and not worth a closing line either
    state["off_topic_count"] += 1
    if state["flagged"]:
        return "", "filtered"  # muted chat: stay quiet until a real message comes
    if state["off_topic_count"] >= OFF_TOPIC_LIMIT:
        state["flagged"] = True
        return templates.turn_text(lang, "closing"), "low"
    question = _pending_or_details(state, short=True)
    if kind == "not_sold":
        return _join(templates.turn_text(lang, "not_sold"), question), "low"
    redirect = templates.turn_text(lang, "redirect", variant=state["off_topic_count"] - 1)
    return _join(redirect, question), "low"


def _units(lang, unit, n):
    return templates._units(lang if lang in templates.PIECE else "en", unit, n)


def _join(*parts):
    return " ".join(p for p in parts if p)


WAITING = {
    "quantity": "how many pieces",
    "confirm_quantity": "them to confirm the quantity",
    "take_available": "if they'll take what's in stock",
    "confirm_order": "them to confirm the order",
    "details": "what they're looking for",
}


def _summary(state):
    """A few words about the chat so far; replaces the history in long chats."""
    item = _compose(state) or "nothing specific yet"
    bits = [f"Buyer wants {item}."]
    if state["shortlist"]:
        bits.append(f"Shown {', '.join(state['shortlist'][:5])}.")
    if state["quantity"]:
        bits.append(f"Quantity {state['quantity']:g} {state['unit'] or ''}.".replace(" .", "."))
    if state["pending_question"]:
        bits.append(f"We asked {WAITING.get(state['pending_question']['expects'], 'a question')}.")
    if state["flagged"]:
        bits.append("Chat muted after off-topic messages.")
    return " ".join(bits)
