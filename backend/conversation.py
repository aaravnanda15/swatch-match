"""A WhatsApp chat with one buyer, turn by turn.

The app keeps the state of each chat (table `conversations`) and decides every
next step, with a template reply whose stock and rate come from the database.
Gemini, when there is a key, labels the newest message (llm.classify_turn) and
then rewrites the reply in a warmer, personal way (llm.compose_reply). The
rewrite is only used if agent/reply_guard.py finds nothing wrong with it.
Without Gemini, a keyword classifier and the templates do the whole job.
"""

import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone

from backend import db, enquiries, llm
from backend.agent import lexicon, reply_guard, templates
from backend.config import ATTRIBUTES, CONFIG

log = logging.getLogger("swatch.chat")

INTENTS = ("answer_to_question", "new_or_changed_request", "question_about_shown_designs",
           "question_about_product_or_terms", "wants_other_designs", "greeting", "off_topic", "abusive_or_nonsense")
ENQUIRY_FIELDS = ("garment_type", "main_colour", "secondary_colour", "pattern", "border", "fabric", "work_type")
OFF_TOPIC_LIMIT = 3
HISTORY = 12  # messages of the chat that Gemini sees
MEMORY_SIZE = 10  # short notes about the buyer ("Buying for a wedding")
MERGE_SECONDS = CONFIG["whatsapp"]["merge_seconds"]

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
# "not this one", "dusra dikhao": the buyer turns down a design they were shown
REJECT = re.compile(r"not (?:this|that|these|those)|n'?t like|another|other (?:one|design|option|colou?r)s?|"
                    r"something else|more (?:designs|options|photos|pics)|kuch aur|aur dikha|dusr[aie] dikha|"
                    r"doosr[aie] dikha|pasand nahi|nahi pasand|और दिखा|दूसरा दिखा|पसंद नहीं|બીજી બતાવ|બીજું બતાવ|"
                    r"પસંદ નથી", re.IGNORECASE)
# "the second one", "pehla wala": which of the designs we showed
ORDINALS = [re.compile(p, re.IGNORECASE) for p in (
    r"\b(?:first|1st|pehl[aie]|pahl[aie])\b|पहल[ाीे]|પહેલ[ીુા]",
    r"\b(?:second|2nd)\b|\b(?:dusr|doosr)[aie] (?:wal|waal|val)[aie]\b|दूसर[ाीे] वाल|બીજ[ીુા] વાળ",
    r"\b(?:third|3rd|teesr[aie]|tisr[aie])\b|तीसर[ाीे]|ત્રીજ[ીુા]",
)]
# Questions about the product or the shop's terms, answered from the catalogue and config.yaml
QUESTION = re.compile(r"\?|\b(?:is it|is this|is the|are they|are these|does it|do you|can you|will you|kya|"
                      r"hai kya|milega|milegi|included|include|kitne din|kab tak|available)\b|क्या|શું", re.IGNORECASE)
TOPICS = {topic: re.compile(p, re.IGNORECASE) for topic, p in {
    "fabric": r"\bpure\b|original|\breal\b|\basli\b|quality|which (?:fabric|material)|kaunsa kapda|"
              r"शुद्ध|असली|ક્વોલિટી|શુદ્ધ|અસલી",
    "delivery": r"deliver|courier|shipping|\bship\b|transport|dispatch|parcel|डिलीवरी|कूरियर|ડિલિવરી|કુરિયર",
    "payment": r"\bcod\b|cash on delivery|payment|\bpay\b|\bupi\b|gpay|paytm|bank transfer|advance|credit|"
               r"udhaa?r|पेमेंट|भुगतान|પેમેન્ટ",
    "minimum_order": r"minimum|\bmoq\b|kam se kam|कम से कम|ઓછામાં ઓછા",
    "returns": r"return|exchange|refund|wapas|vapas|वापस|પાછ",
    "blouse_piece": r"blouse|ब्लाउज|બ્લાઉઝ",
    "samples": r"sample|नमूना|સેમ્પલ",
    "discount": r"discount|best (?:price|rate)|last (?:price|rate)|kam kar|less karo|छूट|डिस्काउंट|ડિસ્કાઉન્ટ",
}.items()}
SHOP = CONFIG.get("shop", {})

OCCASION_NOTES = {"wedding": "Buying for a wedding", "festival": "Buying for a festival",
                  "party": "Buying for a party or function"}
TONE_NOTES = {"formal": ", and formal, because the buyer writes formally",
              "respectful": ", and warm, because the buyer writes with ji, bhaiya or sir"}
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
        "last_buyer_text": "", "filtered_count": 0, "action": None, "reply_source": None, "needs_staff": False,
        "memory": [], "rejected": [], "shown": [], "occasion": None, "name": None, "tone": None, "chosen": None,
        "waiting_for": [],
    }


def get_state(phone):
    return {**new_state(), **(db.get_conversation(phone) or {})}  # older chats lack the newer keys


def unit_of(word):
    if not word:
        return None
    word = word.strip(".").lower()
    return next((unit for unit, words in UNITS.items() if word in words), word)


# ---------- reading the message ----------

def keyword_classify(state, text):
    """(intent, fields, sure). `sure` = a clear case, no need to ask Gemini.
    When it isn't sure, the result is only used if Gemini can't be reached."""
    low = lexicon.translate_digits(text.lower().strip())
    words = WORD.findall(low)
    expects = (state["pending_question"] or {}).get("expects")

    if SPAM.search(low):
        return "off_topic", {"filter": "spam"}, True
    if not re.search(r"[a-z0-9ऀ-ॿ઀-૿]", low):
        return "abusive_or_nonsense", {"filter": "noise"}, True  # emojis or symbols only
    if any(w in lexicon.SWEAR for w in words) or (
            any(w in lexicon.SLANG for w in words) and all(w in lexicon.SLANG or w in ACK for w in words)):
        return "abusive_or_nonsense", {"filter": "rude"}, True  # swearing, or nothing but "yo bro"

    quantity, unit, rest = _number(low)
    if quantity and expects in ("quantity", "confirm_quantity", "take_available"):
        if all(w in FILLER or unit_of(w) in UNITS for w in rest):
            return "answer_to_question", {"quantity": quantity, "unit": unit}, True

    if any(w in NOT_SOLD for w in words) and not lexicon.parse(text)["attributes"]:
        return "off_topic", {"filter": "not_sold"}, True
    yes_no = expects in ("confirm_quantity", "confirm_order", "take_available")
    if yes_no and expects == "take_available" and SIMILAR.search(low):
        return "answer_to_question", {"choice": "similar"}, True
    if yes_no and words and all(w in YES | FILLER | ACK for w in words) and not set(words) & NO:
        return "answer_to_question", {"choice": "yes"}, True
    if yes_no and words and all(w in NO | FILLER for w in words):
        return "answer_to_question", {"choice": "no"}, True
    if words and all(w in ACK for w in words):
        return "off_topic", {"filter": "noise"}, True
    if words and all(w in GREETINGS for w in words):
        return "greeting", {}, True

    # not sure from here on: Gemini decides when it can
    fields = {"refers_to": _referred(state, low)}
    if yes_no and set(words) & (YES | NO):
        return "answer_to_question", {**fields, "choice": "no" if set(words) & NO else "yes"}, False
    topic = _topic(low)
    if topic:
        return "question_about_product_or_terms", {**fields, "topic": topic}, False
    parsed = lexicon.parse(text)
    if parsed["attributes"] or parsed["max_rate"]:
        if state["shortlist"] and STOCK_QUESTION.search(low) and not parsed["attributes"]:
            return "question_about_shown_designs", fields, False
        return "new_or_changed_request", {"attributes": parsed["attributes"], "budget": parsed["max_rate"]}, False
    if state["shortlist"] and STOCK_QUESTION.search(low):
        return "question_about_shown_designs", fields, False
    if state["shortlist"] and REJECT.search(low):
        return "wants_other_designs", fields, False
    if fields["refers_to"]:
        return "answer_to_question", {**fields, "quantity": quantity, "unit": unit}, False
    return "off_topic", fields, False


def _number(low):
    """(quantity, unit, other words) for "50 pcs", "२० पीस", "67 kg"."""
    number = re.search(r"\d+(?:\.\d+)?", low)
    if not number:
        return None, None, WORD.findall(low)
    rest = WORD.findall(low[number.end():]) + WORD.findall(low[:number.start()])
    unit = next((w for w in rest if unit_of(w) in UNITS), None)
    return float(number.group()), unit, rest


def _referred(state, low):
    """The shown design the buyer points at: "D003", "the second one", "pehla wala"."""
    for design_id in re.findall(r"\bd\d+\b", low):
        if design_id.upper() in state["shortlist"]:
            return design_id.upper()
    for position, pattern in enumerate(ORDINALS):
        if position < len(state["shown"]) and pattern.search(low):
            return state["shown"][position]
    return None


def _topic(low):
    """What a question about the product or the shop's terms is about (delivery, COD, fabric...)."""
    if not QUESTION.search(low):
        return None
    return next((topic for topic, pattern in TOPICS.items() if pattern.search(low)), None)


def gemini_classify(state, text, history):
    provider = llm.get_llm()
    if not provider.available:
        return None
    pending = (state["pending_question"] or {}).get("text")
    answer = provider.classify_turn(json.dumps(_state_for_llm(state), ensure_ascii=False), pending,
                                    _history_text(history), text)
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
    if answer.get("refers_to") in state["shortlist"]:
        fields["refers_to"] = answer["refers_to"]
        if not re.search(r"\d", lexicon.translate_digits(text)):
            fields["quantity"] = None  # "the second one" is a position, not 2 pieces
    if answer.get("topic") in (*TOPICS, "other"):
        fields["topic"] = answer["topic"]
    return answer["intent"], fields


def _history_text(history):
    return "\n".join(f"{'buyer' if m['direction'] == 'in' else 'shop'}: {m['text'] or '[photo]'}" for m in history)


def _state_for_llm(state):
    """The state without the bookkeeping, small enough for every call. The notes
    about the buyer stand in for the rule-based summary once there are some."""
    keep = ("enquiry", "budget", "shortlist", "shown", "focus", "rejected", "quantity", "unit", "stage")
    small = {k: state[k] for k in keep}
    if state["memory"]:
        small["memory"] = state["memory"]
    else:
        small["summary"] = state["summary"]
    return small


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
    if g_intent == "answer_to_question" and not state["pending_question"] and not g_fields.get("refers_to"):
        g_intent = "off_topic"
    if g_intent == "new_or_changed_request" and not (g_fields["attributes"] or g_fields["budget"]):
        g_fields["attributes"], g_fields["budget"] = fields.get("attributes", {}), fields.get("budget")
    if g_intent == "question_about_product_or_terms" and not g_fields.get("topic"):
        g_fields["topic"] = fields.get("topic")
    return g_intent, g_fields, "gemini"


# ---------- deciding the reply ----------

def handle_turn(phone, name, text, img=None, image_file=None, buyer=None):
    state = get_state(phone)
    state["turns"] += 1
    state["needs_staff"] = False
    if name:
        state["name"] = templates.first_name(name)
    # a returning buyer: their last design, for "welcome back" (from the database, not the AI)
    returning = None
    if state["stage"] == "done":
        returning = state["focus"]
    elif state["turns"] == 1:
        returning = db.last_design(phone)
    history = db.recent_chat(phone, HISTORY + 1)[:-1]  # the newest message is already stored

    normalized = " ".join(text.lower().split())
    if img is not None:
        intent, fields, read_by = "new_or_changed_request", {}, "photo"
    elif normalized and normalized == state.get("last_buyer_text"):
        intent, fields, read_by = "off_topic", {"filter": "duplicate"}, "keywords"
    else:
        intent, fields, read_by = classify(state, text, history)
    if text:
        state["last_buyer_text"] = normalized
    if text and not fields.get("filter"):
        _notice(state, text)
    pointed = fields.get("refers_to")
    if pointed in state["shortlist"] and intent != "new_or_changed_request":
        state["focus"] = pointed
        state["chosen"] = None if intent == "wants_other_designs" else pointed

    if intent == "new_or_changed_request" and text:
        detected = fields.get("language") or lexicon.detect_language(text)
        if len(WORD.findall(text.lower())) > 1 or state["turns"] == 1:
            state["language"] = detected

    # needs_reply: shown to the seller as New. low: reply drafted, but it can wait.
    # filtered: nothing worth the seller's time (no reply, not shown as New).
    priority = "needs_reply"
    if intent == "new_or_changed_request":
        reply = _new_request(state, phone, text, img, image_file, buyer, fields, returning)
    elif intent == "answer_to_question":
        reply = _answer(state, fields)
    elif intent == "question_about_shown_designs":
        reply = _stock_lines(state, [state["focus"]] if pointed else None)
    elif intent == "question_about_product_or_terms":
        reply = _answer_question(state, fields.get("topic"))
    elif intent == "wants_other_designs":
        reply = _show_other(state)
    elif intent == "greeting":
        reply = _greet(state, returning)
        priority = "low"
    else:
        reply, priority = _off_topic(state, fields.get("filter"))

    if priority == "needs_reply":
        state["off_topic_count"] = 0
        state["flagged"] = False  # a real message un-mutes the chat
    if priority == "filtered":
        state["filtered_count"] += 1
    source = None
    if priority == "needs_reply" and reply:
        reply, source = _write_reply(state, name, text, history, reply, intent)
        _set_outbox(state, reply, intent, source)
    state["reply_source"] = source
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
            "summary": state["summary"], "memory": state["memory"], "reply_source": source,
            "needs_staff": state["needs_staff"],
        }, surface=priority == "needs_reply")
    return {"intent": intent, "reply": reply, "read_by": read_by, "priority": priority,
            "reply_source": source, "state": state}


# ---------- writing the reply ----------

def _write_reply(state, name, text, history, template, intent):
    """The AI's version of the template reply, if it passes every check in
    reply_guard; otherwise the template. Returns (reply, "composed" or "template")."""
    provider = llm.get_llm()
    if not (provider.available and CONFIG["llm"].get("compose_replies")):
        return template, "template"
    started = time.perf_counter()
    facts = _facts(state, template)
    pending = (state["pending_question"] or {}).get("text")
    context = {
        "profile": _profile(state, name),
        "memory": "; ".join(state["memory"]) or state["summary"] or "nothing yet",
        "history": _history_text(history) or "(this is the first message)",
        "message": text or "[photo]",
        "opening": "This is the first reply in the chat: start with a short greeting." if not history
                   else "The chat is already going: do not greet again, go straight in.",
        "action": state["action"] or intent,
        "template": template,
        "facts": json.dumps(facts, ensure_ascii=False),
        "question": f'End with this one question, in your own words: "{pending}"' if pending
                    else "Do not ask a question; the shop is not waiting on one.",
        "language": reply_guard.LANGUAGE_NAMES.get(state["language"], "English"),
        "tone": TONE_NOTES.get(state["tone"], ""),
    }
    problems = []
    for attempt in (1, 2):
        answer = provider.compose_reply(context, problems)
        if not isinstance(answer, dict) or not isinstance(answer.get("reply"), str):
            note = provider.last_error or "no reply from the AI"
            log.info("No AI reply, using the template: %s", note)
            break
        reply = answer["reply"].strip()
        problems = reply_guard.validate_reply(reply, facts, state["language"], template, text)
        if not problems:
            state["needs_staff"] = state["needs_staff"] or answer.get("needs_staff") is True
            _remember(state, answer.get("new_memory"))
            _note_in_trace(state, intent, "composed", "checked: every number and design ID is in stock.csv", started)
            return reply, "composed"
        note = "; ".join(problems)
        log.info("AI reply rejected (try %d of 2): %s", attempt, note)
    _note_in_trace(state, intent, "template", f"plain reply used ({note})", started)
    return template, "template"


def _notice(state, text):
    """What a real message tells us about the buyer: the occasion and how they write."""
    occasion = lexicon.find_occasion(text)
    if occasion:
        state["occasion"] = occasion
        _remember(state, [OCCASION_NOTES[occasion]])
    state["tone"] = lexicon.detect_tone(text) or state["tone"]


def _remember(state, notes):
    if not isinstance(notes, list):
        return
    memory = state["memory"]
    for note in notes:
        note = str(note).strip()[:100]
        if note and note.lower() not in {m.lower() for m in memory}:
            memory.append(note)
    del memory[:-MEMORY_SIZE]


def _facts(state, template):
    """What the AI may say: the designs in play, from the database, and the buyer's numbers."""
    ids = [state["focus"], *state["shown"], *reply_guard.DESIGN_ID.findall(template)]
    designs = []
    for design_id in dict.fromkeys(i for i in ids if i):
        d = db.get_design(design_id)
        if d is None:
            continue
        tags = {k: v for k, v in d["tags"].items() if v not in ("none", "other", "unknown")}
        shown_as = state["shown"].index(design_id) + 1 if design_id in state["shown"] else None
        designs.append({"design_id": design_id, "shown_as": shown_as, "name": d["name"], "rate": d["rate"],
                        "unit": d["unit"],
                        "stock": d["quantity_available"], "garment": tags.get("garment_type"),
                        "fabric": tags.get("fabric"), "colour": tags.get("main_colour"),
                        "pattern": tags.get("pattern"), "border": tags.get("border"), "work": tags.get("work_type")})
    facts = {"designs": designs}
    if state["quantity"]:
        facts["buyer_quantity"] = state["quantity"]
    if (state["pending_question"] or {}).get("value"):
        facts["quantity_in_question"] = state["pending_question"]["value"]
    if state["budget"]:
        facts["buyer_budget_per_piece"] = state["budget"]
    facts["shop_terms"] = {topic: texts["en"] for topic, texts in SHOP.items()}
    return facts


def _profile(state, name):
    bits = [f"WhatsApp name {name!r}" if name else "name unknown",
            f"writes in {reply_guard.LANGUAGE_NAMES.get(state['language'], 'English')}"]
    if state["stage"] == "done":
        bits.append("has just placed an order")
    return ", ".join(bits)


def _note_in_trace(state, intent, source, result, started):
    """Add the writing step to the shortlist's "How this was made" panel (first reply only)."""
    if intent != "new_or_changed_request" or not state["enquiry_id"]:
        return
    enquiry = db.get_enquiry(state["enquiry_id"])
    answer = enquiry and enquiry["answer"]
    if not answer:
        return
    answer["trace"].append({
        "step": len(answer["trace"]) + 1, "tool": "compose_reply",
        "why": "Write the reply in the buyer's language, about what they said",
        "input": f"plain reply + facts from stock.csv ({state['action']})",
        "output": f"{'written by AI' if source == 'composed' else 'template'}, {result}",
        "ms": int((time.perf_counter() - started) * 1000),
    })
    db.save_answer(state["enquiry_id"], answer)


def _new_request(state, phone, text, img, image_file, buyer, fields, returning=None):
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
        query_text = text if img is not None else _query_text(state) or text
        answer = enquiries.run(query_text, img, image_file, whatsapp=buyer, display_text=text)
    adopt_answer(state, answer)
    lang = state["language"]
    picks = _good_picks(answer, state["rejected"])
    best = answer["results"][0] if answer["results"] else None
    if best and not best["in_stock"] and best["label"] in ("very_close", "similar"):
        _wait_for(state, best["design_id"])  # their best match is out of stock: tell them when it's back

    if answer["clarifying_question"]:
        state["pending_question"] = {"text": answer["clarifying_question"], "expects": "details"}
        state["stage"] = "browsing"
        state["action"] = "ask_for_details"
        return answer["clarifying_question"]
    if not picks:
        text = _join(_say(state, "no_more"), _ask(state, "ask_details", "details"))
        state["action"] = "nothing_in_stock_ask_details"
        return text
    _ask(state, "ask_quantity", "quantity", short_key="ask_quantity_short")
    state["stage"] = "asked_quantity"
    state["quantity"] = state["unit"] = None
    state["reply_picks"] = state["shown"] = picks
    state["action"] = "show_closest_designs" if answer["no_match"] else "show_matching_designs"
    welcome = _welcome(state, returning)
    text = templates.draft_reply(lang, [db.get_design(d) for d in picks], no_match=answer["no_match"],
                                 buyer=templates.address(lang, state["name"]),
                                 occasion=templates.occasion_words(lang, state["occasion"]),
                                 greet=state["turns"] == 1 and not welcome)
    return _toned(state, _join(welcome, text))


def _set_outbox(state, reply, intent, source=None):
    """The reply waiting for the seller's approval (what Reply to all sends). If the
    buyer writes again before the seller has replied, the design photos picked
    for the unsent shortlist still go with the newer reply."""
    previous = state.get("outbox") or {}
    picks = state.pop("reply_picks", None) if intent == "new_or_changed_request" else None
    first = None  # the unsent shortlist reply, which still has to reach the buyer
    if picks is None:
        unsent = previous.get("enquiry_id") == state["enquiry_id"] and _unsent(state["enquiry_id"])
        picks = previous.get("picked", []) if unsent else []
        if unsent:
            first = previous.get("first") or (previous["text"] if previous.get("intent") == "new_or_changed_request" else None)
    state["outbox"] = {"enquiry_id": state["enquiry_id"], "text": _join_blocks(first, reply), "first": first,
                       "picked": picks or [], "language": state["language"], "intent": intent,
                       "source": source, "needs_staff": state["needs_staff"]}


def _join_blocks(*parts):
    return "\n\n".join(p for p in parts if p)


def _unsent(enquiry_id):
    enquiry = db.get_enquiry(enquiry_id) if enquiry_id else None
    return bool(enquiry) and enquiry["status"] == "new"


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
    state["chosen"] = None
    picks = _good_picks(answer, state["rejected"])
    state["focus"] = picks[0] if picks else None


def _good_picks(answer, skip=()):
    """Up to 3 good matches in stock (designs the buyer turned down are skipped)."""
    if answer["clarifying_question"]:
        return []
    fresh = [r for r in answer["results"] if r["in_stock"] and r["design_id"] not in skip]
    good = [r["design_id"] for r in fresh if r["label"] in ("very_close", "similar")]
    if good:
        return good[:3]
    return [fresh[0]["design_id"]] if fresh else []


def _query_text(state):
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

    if fields.get("quantity") and (expects in ("quantity", "confirm_quantity", "take_available")
                                   or fields.get("refers_to")):
        return _quantity(state, fields["quantity"], fields.get("unit"))
    if fields.get("refers_to") and not choice:  # "the second one"
        lead = _say(state, "good_choice")
        return _join(lead, _stock_check(state, state["quantity"]) if state["quantity"] else _ask_quantity(state))
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


def _answer_question(state, topic):
    """Fabric from the catalogue, delivery, payment and so on from the shop's terms
    in config.yaml. Anything else is left for staff to confirm."""
    design = _focus(state)
    fabric = design and design["tags"].get("fabric")
    if topic == "fabric" and fabric and fabric != "unknown":
        answer = _say(state, "fabric_answer", name=design["name"], design=design["design_id"], fabric=fabric)
    elif topic in SHOP:
        answer = SHOP[topic].get(state["language"]) or SHOP[topic]["en"]
    else:
        answer = _say(state, "staff_confirm")
        state["needs_staff"] = True
    text = _join(answer, _pending_or_details(state, short=True))
    state["action"] = f"answer_question_about_{topic or 'something_not_on_file'}"
    return text


def _focus(state):
    return db.get_design(state["focus"]) if state["focus"] else None


def _quantity(state, quantity, unit):
    design = _focus(state)
    if design is None:
        return _ask_details(state)
    n = int(quantity) if float(quantity).is_integer() else quantity
    if unit and unit_of(unit) != unit_of(design["unit"]):
        lang = state["language"]
        text = _ask(state, "unit_mismatch", "confirm_quantity", short_key="confirm_short", value=n,
                    unit=_units(lang, design["unit"], 1), buyer_unit=unit, n=n, units=_units(lang, design["unit"], n))
        state["stage"] = "confirming"
        state["action"] = "unit_mismatch"
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
        _wait_for(state, design["design_id"])
        text = _ask(state, "out", "take_available", short_key="similar_short", **values)
        state["action"] = "stock_check_out_of_stock"
    elif n > available:
        text = _ask(state, "short", "take_available", short_key="take_short", value=available, **values)
        state["action"] = "stock_check_short"
    else:
        text = _ask(state, "in_stock", "confirm_order", short_key="book_short", value=n, **values)
        state["action"] = "stock_check_in_stock"
    return text


def _confirmed(state, n):
    design = _focus(state)
    lang = state["language"]
    state["quantity"], state["stage"], state["pending_question"] = n, "done", None
    state["action"] = "order_confirmed"
    return _say(state, "confirmed", n=n, units=_units(lang, design["unit"], n), name=design["name"],
                design=design["design_id"])


def _show_other(state):
    """The buyer turned down the design we were talking about ("not this one")."""
    if state["focus"] and state["focus"] not in state["rejected"]:
        state["rejected"].append(state["focus"])
    return _show_similar(state)


def _show_similar(state):
    skip = {state["focus"], *state["rejected"]}
    others = [d for d in (db.get_design(i) for i in state["shortlist"] if i not in skip)
              if d and d["quantity_available"] > 0]
    others.sort(key=lambda d: d["design_id"] in state["shown"])  # ones they haven't seen first
    if not others:
        text = _join(_say(state, "no_more"), _ask_details(state))
        state["action"] = "no_other_designs"
        return text
    state["focus"] = others[0]["design_id"]
    state["shown"] = [d["design_id"] for d in others[:3]]
    text = _join(_stock_lines(state, state["shown"], ask=False), _ask_quantity(state))
    state["action"] = "show_similar"
    return text


def _stock_lines(state, design_ids=None, ask=True):
    lang = state["language"]
    designs = [db.get_design(i) for i in (design_ids or state["shortlist"][:3])]
    designs = [d for d in designs if d]
    if not designs:
        return _ask_details(state)
    lines = [_say(state, "stock_intro")]
    for d in designs:
        lines.append(templates.turn_text(lang, "stock_line", design=d["design_id"], name=d["name"],
                                         available=d["quantity_available"], rate=templates._rupees(d["rate"]),
                                         unit=_units(lang, d["unit"], 1),
                                         units=_units(lang, d["unit"], d["quantity_available"])))
    text = "\n".join(lines)
    text = f"{text}\n\n{_pending_or_details(state, short=True)}" if ask else text
    state["action"] = "answer_stock_question"
    return text


def _ask_quantity(state):
    text = _ask(state, "ask_quantity", "quantity", short_key="ask_quantity_short")
    state["stage"] = "asked_quantity"
    state["action"] = "ask_quantity"
    return text


def _ask_details(state):
    text = _ask(state, "ask_details", "details")
    state["stage"] = "browsing"
    state["action"] = "ask_what_they_want"
    return text


def _ask(state, key, expects, short_key=None, value=None, **values):
    """Ask the buyer something, and keep the template so it can be asked again in other words."""
    text = _say(state, key, **values)
    state["pending_question"] = {"text": text, "key": key, "short_key": short_key, "values": values,
                                 "expects": expects, "value": value}
    return text


def _pending_or_details(state, short=False):
    """The question we're waiting on (its short form when repeating it)."""
    pending = state["pending_question"]
    if not pending:
        return _ask_details(state)
    state["action"] = "repeat_our_question"
    key = (short and pending.get("short_key")) or pending.get("key")
    if key:
        return _say(state, key, **pending.get("values", {}))
    return pending.get("short", pending["text"]) if short else pending["text"]


def _say(state, key, **values):
    """A template line with the buyer's name, the item and the occasion filled in,
    worded differently from the reply the buyer just got."""
    lang = state["language"]
    item, plural, kind = templates.item_words(lang, state["enquiry"])
    if state["chosen"] and state["chosen"] == state["focus"]:
        design = db.get_design(state["chosen"])
        item = f"{design['name']} ({design['design_id']})" if design else item
    values = {"buyer": templates.address(lang, state["name"]), "item": item, "plural": plural, "kind": kind,
              "occasion": templates.occasion_words(lang, state["occasion"]), **values}
    for i in range(templates.variant_count(lang, key)):
        text = templates.turn_text(lang, key, state["turns"] + i, **values)
        if text not in state["last_reply"]:
            break
    return _toned(state, text)


def _toned(state, text):
    return templates.no_emoji(text) if state["tone"] == "formal" else text


def _greet(state, returning=None):
    """Hello back. In the middle of a chat, pick up where it left off."""
    hello = _welcome(state, returning) or _say(
        state, "welcome_back" if state["pending_question"] and state["enquiry"] else "greeting")
    return _join(hello, _pending_or_details(state, short=True))


def _welcome(state, design_id):
    design = db.get_design(design_id) if design_id else None
    return _say(state, "welcome_back_design", name=design["name"], design=design_id) if design else ""


def _wait_for(state, design_id):
    if design_id not in state["waiting_for"]:
        state["waiting_for"].append(design_id)


def back_in_stock(design_id):
    """Staff raised a design's stock above 0: draft a "it's back" message for every
    buyer who wanted it. Staff approve it in the Inbox like any other reply."""
    design = db.get_design(design_id)
    drafted = 0
    for conv in db.list_conversations():
        state = {**new_state(), **conv["state"]}
        if design is None or design_id not in state["waiting_for"] or not state["enquiry_id"]:
            continue
        state["waiting_for"].remove(design_id)
        state["focus"] = state["chosen"] = design_id
        lang = state["language"]
        reply = _say(state, "back_in_stock", name=design["name"], design=design_id,
                     available=design["quantity_available"], units=_units(lang, design["unit"], design["quantity_available"]),
                     rate=templates._rupees(design["rate"]), unit=_units(lang, design["unit"], 1))
        _ask(state, "ask_quantity", "quantity", short_key="ask_quantity_short")
        state["stage"], state["action"], state["last_reply"] = "asked_quantity", "back_in_stock", reply
        _set_outbox(state, reply, "back_in_stock", "template")
        if design_id in state["shortlist"] and not state["outbox"]["picked"]:
            state["outbox"]["picked"] = [design_id]  # its photo goes with the message
        state["summary"] = _summary(state)
        db.save_conversation(conv["phone"], state)
        db.set_followup(state["enquiry_id"], {
            "buyer_text": None, "intent": "back_in_stock", "reply": reply, "read_by": "app",
            "priority": "needs_reply", "flagged": False, "stage": state["stage"], "summary": state["summary"],
            "memory": state["memory"], "reply_source": "template", "needs_staff": False,
        })
        drafted += 1
    return drafted


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
        return _say(state, "closing"), "low"
    question = _pending_or_details(state)
    if kind == "not_sold":
        return _join(_say(state, "not_sold"), question), "low"
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
    item = _query_text(state) or "nothing specific yet"
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
