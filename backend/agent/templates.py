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


# ---------- follow-up turns in a chat ----------
# Every reply the chat bot drafts comes from here. Numbers are filled in by
# backend/conversation.py from the database (stock.csv), never by an LLM.

TURN = {
    "en": {
        "ask_quantity": "How many pieces of the {item} do you need?",
        "ask_details": "What are you looking for today? A photo, the colour or the type (saree, dupatta) helps.",
        "unit_mismatch": "{plural} are sold per {unit}. Do you mean {n} {units} of the {item}?",
        "confirm_short": "Do you mean {n} {units} of the {item}?",
        "in_stock": "Yes, we have {available} {units} of {name} ({design}) at {rate} per {unit}. Shall I confirm {n} {units_n} for you?",
        "short": "We have {available} {units} of {design} in stock. Would you like those {available}, or should I show similar designs?",
        "out": "{name} ({design}) is out of stock right now. Should I show similar designs?",
        "confirmed": "Thank you. We will confirm {n} {units} of {name} ({design}) and send you the details shortly 🙏",
        "stock_line": "{design} {name}: {available} {units} in stock, {rate} per {unit}",
        "stock_intro": "Here is what we have:",
        "redirect": "I can help with {plural_lower}.",
        "greeting": "Namaste 🙏",
        "closing": "I will leave it here for now. Our team will get back to you. Thank you 🙏",
        "no_more": "Sorry, I don't have more designs like this in stock right now.",
    },
    "hinglish": {
        "ask_quantity": "{item} ke kitne piece chahiye?",
        "ask_details": "Aapko kya chahiye? Photo, colour ya type (saree, dupatta) bata dijiye.",
        "unit_mismatch": "{plural} piece mein milti hai. Kya aapko {item} ke {n} piece chahiye?",
        "confirm_short": "Kya aapko {item} ke {n} piece chahiye?",
        "in_stock": "Haan, {name} ({design}) ke {available} piece stock mein hain, {rate} per piece. Kya {n} piece confirm kar dein?",
        "short": "{design} ke {available} piece stock mein hain. Kya aap yeh {available} lenge, ya milte-julte design dikhayein?",
        "out": "{name} ({design}) abhi stock mein nahi hai. Kya milte-julte design dikhayein?",
        "confirmed": "Dhanyavaad. {name} ({design}) ke {n} piece confirm karke details bhejte hain 🙏",
        "stock_line": "{design} {name}: {available} piece stock mein, {rate} per piece",
        "stock_intro": "Abhi stock mein:",
        "redirect": "Main {plural_lower} mein madad kar sakta hoon.",
        "greeting": "Namaste 🙏",
        "closing": "Abhi ke liye itna hi. Hamari team aapse baat karegi. Dhanyavaad 🙏",
        "no_more": "Maaf kijiye, abhi aise aur design stock mein nahi hain.",
    },
    "hi": {
        "ask_quantity": "{item} के कितने पीस चाहिए?",
        "ask_details": "आपको क्या चाहिए? फोटो, रंग या प्रकार (साड़ी, दुपट्टा) बता दीजिए।",
        "unit_mismatch": "{plural} पीस में मिलती है। क्या आपको {item} के {n} पीस चाहिए?",
        "confirm_short": "क्या आपको {item} के {n} पीस चाहिए?",
        "in_stock": "जी हाँ, {name} ({design}) के {available} पीस स्टॉक में हैं, {rate} प्रति पीस। क्या {n} पीस कन्फ़र्म कर दें?",
        "short": "{design} के {available} पीस स्टॉक में हैं। क्या आप ये {available} लेंगे, या मिलते-जुलते डिज़ाइन दिखाएँ?",
        "out": "{name} ({design}) अभी स्टॉक में नहीं है। क्या मिलते-जुलते डिज़ाइन दिखाएँ?",
        "confirmed": "धन्यवाद। {name} ({design}) के {n} पीस कन्फ़र्म करके जानकारी भेजते हैं 🙏",
        "stock_line": "{design} {name}: {available} पीस स्टॉक में, {rate} प्रति पीस",
        "stock_intro": "अभी स्टॉक में:",
        "redirect": "मैं {plural_lower} में मदद कर सकता हूँ।",
        "greeting": "नमस्ते 🙏",
        "closing": "अभी के लिए इतना ही। हमारी टीम आपसे बात करेगी। धन्यवाद 🙏",
        "no_more": "माफ़ कीजिए, अभी ऐसे और डिज़ाइन स्टॉक में नहीं हैं।",
    },
    "gu": {
        "ask_quantity": "{item} ના કેટલા પીસ જોઈએ?",
        "ask_details": "તમને શું જોઈએ છે? ફોટો, રંગ કે પ્રકાર (સાડી, દુપટ્ટો) જણાવો.",
        "unit_mismatch": "{plural} પીસમાં મળે છે. શું તમને {item} ના {n} પીસ જોઈએ છે?",
        "confirm_short": "શું તમને {item} ના {n} પીસ જોઈએ છે?",
        "in_stock": "હા, {name} ({design}) ના {available} પીસ સ્ટોકમાં છે, {rate} પ્રતિ પીસ. {n} પીસ કન્ફર્મ કરીએ?",
        "short": "{design} ના {available} પીસ સ્ટોકમાં છે. આ {available} લેશો, કે મળતી ડિઝાઇન બતાવીએ?",
        "out": "{name} ({design}) હાલ સ્ટોકમાં નથી. મળતી ડિઝાઇન બતાવીએ?",
        "confirmed": "આભાર. {name} ({design}) ના {n} પીસ કન્ફર્મ કરીને વિગતો મોકલીએ છીએ 🙏",
        "stock_line": "{design} {name}: {available} પીસ સ્ટોકમાં, {rate} પ્રતિ પીસ",
        "stock_intro": "હાલ સ્ટોકમાં:",
        "redirect": "હું {plural_lower} માટે મદદ કરી શકું છું.",
        "greeting": "નમસ્તે 🙏",
        "closing": "હાલ પૂરતું આટલું. અમારી ટીમ તમારો સંપર્ક કરશે. આભાર 🙏",
        "no_more": "માફ કરશો, હાલ આવી બીજી ડિઝાઇન સ્ટોકમાં નથી.",
    },
}

# What we call the item in each language ("red saree", "लाल साड़ी")
GARMENT_WORDS = {
    "en": {"saree": ("saree", "Sarees"), "dupatta": ("dupatta", "Dupattas"), "lehenga": ("lehenga", "Lehengas"),
           "kurti": ("kurti", "Kurtis"), "blouse piece": ("blouse piece", "Blouse pieces"),
           "dress material": ("dress material", "Dress materials"), "fabric": ("fabric", "Fabrics")},
    "hi": {"saree": ("साड़ी", "साड़ियाँ"), "dupatta": ("दुपट्टा", "दुपट्टे"), "lehenga": ("लहंगा", "लहंगे"),
           "kurti": ("कुर्ती", "कुर्तियाँ"), "fabric": ("कपड़ा", "कपड़े")},
    "gu": {"saree": ("સાડી", "સાડીઓ"), "dupatta": ("દુપટ્ટો", "દુપટ્ટા"), "lehenga": ("લહેંગો", "લહેંગા"),
           "kurti": ("કુર્તી", "કુર્તીઓ"), "fabric": ("કાપડ", "કાપડ")},
}
COLOUR_WORDS = {
    "hi": {"red": "लाल", "maroon": "मैरून", "pink": "गुलाबी", "orange": "नारंगी", "yellow": "पीली", "gold": "सुनहरी",
           "green": "हरी", "blue": "नीली", "navy": "नेवी", "purple": "जामुनी", "white": "सफ़ेद", "cream": "क्रीम",
           "black": "काली", "grey": "स्लेटी", "brown": "भूरी", "silver": "चांदी", "multicolour": "रंगीन"},
    "gu": {"red": "લાલ", "maroon": "મરૂન", "pink": "ગુલાબી", "orange": "કેસરી", "yellow": "પીળી", "gold": "સોનેરી",
           "green": "લીલી", "blue": "વાદળી", "navy": "નેવી", "purple": "જાંબલી", "white": "સફેદ", "cream": "ક્રીમ",
           "black": "કાળી", "grey": "રાખોડી", "brown": "કથ્થઈ", "silver": "ચાંદી", "multicolour": "રંગીન"},
}
HINGLISH_COLOURS = {"red": "laal", "blue": "neeli", "green": "hari", "yellow": "peeli", "black": "kaali",
                    "white": "safed", "pink": "gulabi", "maroon": "maroon", "gold": "golden"}


def item_words(language, enquiry):
    """("red saree", "Sarees", "sarees") in the reply's language."""
    garment = enquiry.get("garment_type") or "saree"
    colour = enquiry.get("main_colour")
    lang = language if language in GARMENT_WORDS else "en"
    words = GARMENT_WORDS[lang].get(garment) or GARMENT_WORDS["en"].get(garment, (garment, garment.title() + "s"))
    if language == "hinglish":
        words = GARMENT_WORDS["en"].get(garment, words)
        colour_word = HINGLISH_COLOURS.get(colour, colour)
    elif lang in COLOUR_WORDS:
        colour_word = COLOUR_WORDS[lang].get(colour, colour)
    else:
        colour_word = colour
    item = f"{colour_word} {words[0]}" if colour_word else words[0]
    # Hindi, Gujarati and Hinglish read better with the singular ("Saree piece mein milti hai")
    plural = words[1] if language == "en" else words[0][:1].upper() + words[0][1:]
    return item, plural, words[1].lower()


def turn_text(language, key, **values):
    t = TURN.get(language, TURN["en"])
    text = t[key].format(**values)
    return text[:1].upper() + text[1:]
