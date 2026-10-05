"""Fixed wording for messages to the buyer, in English, Hindi, Hinglish and Gujarati."""

# What we ask depends on what is missing; {known} is what we did understand.
CLARIFY = {
    "en": {
        "nothing": "Could you send a photo of the design you want, or tell us the colour, the type (saree, dupatta, dress material) and your budget?",
        "known": "Got it, {known}. Could you send a photo, or tell us the colour and pattern you want, and your budget per piece?",
    },
    "hinglish": {
        "nothing": "Kya aap design ki photo bhej sakte hain? Ya colour, type (saree, dupatta, dress material) aur budget bata dijiye.",
        "known": "Theek hai, {known}. Kya aap photo bhej sakte hain, ya colour, design aur per piece budget bata dijiye?",
    },
    "hi": {
        "nothing": "क्या आप डिज़ाइन की फोटो भेज सकते हैं? या रंग, प्रकार (साड़ी, दुपट्टा, ड्रेस मटीरियल) और बजट बता दीजिए।",
        "known": "ठीक है, {known}। क्या आप फोटो भेज सकते हैं, या रंग, डिज़ाइन और प्रति पीस बजट बता दीजिए?",
    },
    "gu": {
        "nothing": "શું તમે ડિઝાઇનનો ફોટો મોકલી શકો? અથવા રંગ, પ્રકાર (સાડી, દુપટ્ટો, ડ્રેસ મટીરીયલ) અને બજેટ જણાવો.",
        "known": "બરાબર, {known}. શું તમે ફોટો મોકલી શકો, અથવા રંગ, ડિઝાઇન અને પ્રતિ પીસ બજેટ જણાવો?",
    },
}


def clarifying_question(language, attributes):
    texts = CLARIFY.get(language, CLARIFY["en"])
    known = [v for v in attributes.values() if v not in ("none", "other", "unknown")]
    if known:
        return texts["known"].format(known=" ".join(known))
    return texts["nothing"]


REPLY = {
    "en": {
        "hello": "Namaste! Thank you for your enquiry.",
        "intro": "Is it one of these?",
        "intro_no_match": "We don't have the exact design right now. These are the closest we have:",
        "rate": "{rate} per {unit}",
        "stock": "{quantity} {units} available",
        "only": "only {quantity} {units} available",
        "out": "currently out of stock",
        "ask": "Please reply with the number and how many pieces you need.",
        "shade": "Colours can look slightly different in photos.",
    },
    "hinglish": {
        "hello": "Namaste! Enquiry ke liye dhanyavaad.",
        "intro": "Kya inmein se koi chahiye?",
        "intro_no_match": "Exact design abhi stock mein nahi hai. Sabse milte-julte yeh hain:",
        "rate": "{rate} per {unit}",
        "stock": "{quantity} {units} available",
        "only": "sirf {quantity} {units} available",
        "out": "abhi stock mein nahi",
        "ask": "Number aur kitne piece chahiye, bata dijiye.",
        "shade": "Photo mein shade thoda alag lag sakta hai.",
    },
    "hi": {
        "hello": "नमस्ते! पूछताछ के लिए धन्यवाद।",
        "intro": "क्या इनमें से कोई चाहिए?",
        "intro_no_match": "बिल्कुल यही डिज़ाइन अभी स्टॉक में नहीं है। सबसे मिलते-जुलते ये हैं:",
        "rate": "{rate} प्रति {unit}",
        "stock": "{quantity} {units} उपलब्ध",
        "only": "सिर्फ़ {quantity} {units} उपलब्ध",
        "out": "अभी स्टॉक में नहीं",
        "ask": "कृपया नंबर और कितने पीस चाहिए, बताइए।",
        "shade": "फोटो में रंग थोड़ा अलग दिख सकता है।",
    },
    "gu": {
        "hello": "નમસ્તે! પૂછપરછ માટે આભાર.",
        "intro": "શું આમાંથી કોઈ જોઈએ છે?",
        "intro_no_match": "બરાબર આ જ ડિઝાઇન હાલ સ્ટોકમાં નથી. સૌથી નજીકની આ છે:",
        "rate": "{rate} પ્રતિ {unit}",
        "stock": "{quantity} {units} ઉપલબ્ધ",
        "only": "ફક્ત {quantity} {units} ઉપલબ્ધ",
        "out": "હાલ સ્ટોકમાં નથી",
        "ask": "કૃપા કરીને નંબર અને કેટલા પીસ જોઈએ તે જણાવો.",
        "shade": "ફોટામાં રંગ થોડો અલગ લાગી શકે છે.",
    },
}

# How the unit "piece" is written in each language (other units stay as in stock.csv)
PIECE = {"en": ("piece", "pieces"), "hinglish": ("piece", "piece"), "hi": ("पीस", "पीस"), "gu": ("પીસ", "પીસ")}

LANGUAGES = tuple(REPLY)


def _units(language, unit, quantity):
    if unit == "piece":
        one, many = PIECE[language]
        return one if quantity == 1 else many
    return unit


def _rupees(value):
    whole = str(int(round(value)))
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return "₹" + whole


def draft_reply(language, designs, no_match=False, min_quantity=None):
    """designs: list of dicts straight from the database (design_id, name, rate, unit, quantity_available)."""
    t = REPLY.get(language, REPLY["en"])
    lines = [t["hello"], t["intro_no_match"] if no_match else t["intro"], ""]
    for i, d in enumerate(designs, start=1):
        quantity = d["quantity_available"]
        rate = t["rate"].format(rate=_rupees(d["rate"]), unit=_units(language, d["unit"], 1))
        if quantity <= 0:
            stock = t["out"]
        elif min_quantity and quantity < min_quantity:
            stock = t["only"].format(quantity=quantity, units=_units(language, d["unit"], quantity))
        else:
            stock = t["stock"].format(quantity=quantity, units=_units(language, d["unit"], quantity))
        lines.append(f"{i}. {d['name']} ({d['design_id']}): {rate}, {stock}")
    lines += ["", t["ask"], t["shade"]]
    return "\n".join(lines)
