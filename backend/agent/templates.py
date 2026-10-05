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
        "hello": "Namaste 🙏 Here's what we have for you:",
        "hello_no_match": "Namaste 🙏 We don't have that exact one right now, but these are close:",
        "rate": "{rate} a {unit}",
        "stock": "{quantity} in stock",
        "only": "only {quantity} left",
        "out": "out of stock right now",
        "ask": "How many pieces would you like?",
        "shade": "(Colours can look a little different on a phone screen.)",
    },
    "hinglish": {
        "hello": "Namaste ji 🙏 Yeh designs abhi available hain:",
        "hello_no_match": "Namaste ji 🙏 Bilkul yahi design abhi nahi hai, par yeh kaafi milte-julte hain:",
        "rate": "{rate} per {unit}",
        "stock": "{quantity} stock mein",
        "only": "sirf {quantity} bache hain",
        "out": "abhi stock mein nahi",
        "ask": "Kitne piece chahiye?",
        "shade": "(Photo mein colour thoda alag dikh sakta hai.)",
    },
    "hi": {
        "hello": "नमस्ते जी 🙏 ये डिज़ाइन अभी उपलब्ध हैं:",
        "hello_no_match": "नमस्ते जी 🙏 बिल्कुल यही डिज़ाइन अभी नहीं है, पर ये काफ़ी मिलते-जुलते हैं:",
        "rate": "{rate} प्रति {unit}",
        "stock": "{quantity} स्टॉक में",
        "only": "सिर्फ़ {quantity} बचे हैं",
        "out": "अभी स्टॉक में नहीं",
        "ask": "कितने पीस चाहिए?",
        "shade": "(फोटो में रंग थोड़ा अलग दिख सकता है।)",
    },
    "gu": {
        "hello": "નમસ્તે 🙏 આ ડિઝાઇન હાલ ઉપલબ્ધ છે:",
        "hello_no_match": "નમસ્તે 🙏 બરાબર આ જ ડિઝાઇન હાલ નથી, પણ આ ઘણી મળતી આવે છે:",
        "rate": "{rate} પ્રતિ {unit}",
        "stock": "{quantity} સ્ટોકમાં",
        "only": "ફક્ત {quantity} બાકી",
        "out": "હાલ સ્ટોકમાં નથી",
        "ask": "કેટલા પીસ જોઈએ?",
        "shade": "(ફોટામાં રંગ થોડો અલગ લાગી શકે.)",
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
    lines = [t["hello_no_match"] if no_match else t["hello"], ""]
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
        "ask_quantity": "How many pieces of the {item} would you like?",
        "ask_details": "What are you looking for today? A photo, the colour or the type (saree, dupatta) is enough.",
        "unit_mismatch": "{plural} are sold by the {unit}, not by {buyer_unit}. Did you mean {n} {units} of the {item}?",
        "confirm_short": "Did you mean {n} {units} of the {item}?",
        "in_stock": "Yes, {name} ({design}) is in stock: {available} {units} at {rate} a {unit}. Shall I book {n} {units_n} for you?",
        "short": "We only have {available} {units} of {design} right now. Would you like all {available}, or shall I show you a few similar designs?",
        "out": "Sorry, {name} ({design}) is out of stock right now. Shall I show you a few similar designs?",
        "confirmed": "Done! {n} {units} of {name} ({design}) noted. We'll send you the details shortly 🙏",
        "stock_line": "• {design} {name}: {available} in stock, {rate} a {unit}",
        "stock_intro": "Here's the stock right now:",
        "redirect": ["Sorry, I didn't quite get that.", "We only deal in sarees, dupattas and fabric here.", "Happy to help when you're ready."],
        "not_sold": "Sorry, we only deal in sarees, dupattas and fabric.",
        "greeting": "Namaste 🙏",
        "closing": "No problem. Message us whenever you're ready, we're happy to help 🙏",
        "no_more": "Sorry, nothing else like this in stock right now.",
    },
    "hinglish": {
        "ask_quantity": "{item} ke kitne piece chahiye?",
        "ask_details": "Aapko kya chahiye? Photo, colour ya type (saree, dupatta) bata dijiye.",
        "unit_mismatch": "{plural} piece mein milti hai, {buyer_unit} mein nahi. Kya aapko {item} ke {n} piece chahiye?",
        "confirm_short": "Kya aapko {item} ke {n} piece chahiye?",
        "in_stock": "Haan ji, {name} ({design}) available hai: {available} piece, {rate} per piece. {n} piece book kar dein?",
        "short": "{design} ke abhi sirf {available} piece hain. Saare {available} le lenge, ya milte-julte design dikhayein?",
        "out": "Maaf kijiye, {name} ({design}) abhi stock mein nahi hai. Milte-julte design dikhayein?",
        "confirmed": "Ho gaya! {name} ({design}) ke {n} piece note kar liye. Details thodi der mein bhejte hain 🙏",
        "stock_line": "• {design} {name}: {available} stock mein, {rate} per piece",
        "stock_intro": "Abhi ka stock:",
        "redirect": ["Maaf kijiye, samajh nahi aaya.", "Hum sirf saree, dupatta aur kapda rakhte hain.", "Jab ready ho, bata dijiye."],
        "not_sold": "Maaf kijiye, hum sirf saree, dupatta aur kapda rakhte hain.",
        "greeting": "Namaste ji 🙏",
        "closing": "Koi baat nahi. Jab bhi chahiye, message kar dijiye 🙏",
        "no_more": "Maaf kijiye, abhi aise aur design stock mein nahi hain.",
    },
    "hi": {
        "ask_quantity": "{item} के कितने पीस चाहिए?",
        "ask_details": "आपको क्या चाहिए? फोटो, रंग या प्रकार (साड़ी, दुपट्टा) बता दीजिए।",
        "unit_mismatch": "{plural} पीस में मिलती है, {buyer_unit} में नहीं। क्या आपको {item} के {n} पीस चाहिए?",
        "confirm_short": "क्या आपको {item} के {n} पीस चाहिए?",
        "in_stock": "जी हाँ, {name} ({design}) उपलब्ध है: {available} पीस, {rate} प्रति पीस। {n} पीस बुक कर दें?",
        "short": "{design} के अभी सिर्फ़ {available} पीस हैं। सारे {available} लेंगे, या मिलते-जुलते डिज़ाइन दिखाएँ?",
        "out": "माफ़ कीजिए, {name} ({design}) अभी स्टॉक में नहीं है। मिलते-जुलते डिज़ाइन दिखाएँ?",
        "confirmed": "हो गया! {name} ({design}) के {n} पीस नोट कर लिए। जानकारी थोड़ी देर में भेजते हैं 🙏",
        "stock_line": "• {design} {name}: {available} स्टॉक में, {rate} प्रति पीस",
        "stock_intro": "अभी का स्टॉक:",
        "redirect": ["माफ़ कीजिए, समझ नहीं आया।", "हम सिर्फ़ साड़ी, दुपट्टा और कपड़ा रखते हैं।", "जब तैयार हों, बता दीजिए।"],
        "not_sold": "माफ़ कीजिए, हम सिर्फ़ साड़ी, दुपट्टा और कपड़ा रखते हैं।",
        "greeting": "नमस्ते जी 🙏",
        "closing": "कोई बात नहीं। जब भी चाहिए, मैसेज कर दीजिए 🙏",
        "no_more": "माफ़ कीजिए, अभी ऐसे और डिज़ाइन स्टॉक में नहीं हैं।",
    },
    "gu": {
        "ask_quantity": "{item} ના કેટલા પીસ જોઈએ?",
        "ask_details": "તમને શું જોઈએ છે? ફોટો, રંગ કે પ્રકાર (સાડી, દુપટ્ટો) જણાવો.",
        "unit_mismatch": "{plural} પીસમાં મળે છે, {buyer_unit}માં નહીં. શું તમને {item} ના {n} પીસ જોઈએ છે?",
        "confirm_short": "શું તમને {item} ના {n} પીસ જોઈએ છે?",
        "in_stock": "હા, {name} ({design}) ઉપલબ્ધ છે: {available} પીસ, {rate} પ્રતિ પીસ. {n} પીસ બુક કરીએ?",
        "short": "{design} ના હાલ ફક્ત {available} પીસ છે. બધા {available} લેશો, કે મળતી ડિઝાઇન બતાવીએ?",
        "out": "માફ કરશો, {name} ({design}) હાલ સ્ટોકમાં નથી. મળતી ડિઝાઇન બતાવીએ?",
        "confirmed": "થઈ ગયું! {name} ({design}) ના {n} પીસ નોંધી લીધા. વિગતો થોડી વારમાં મોકલીએ છીએ 🙏",
        "stock_line": "• {design} {name}: {available} સ્ટોકમાં, {rate} પ્રતિ પીસ",
        "stock_intro": "હાલનો સ્ટોક:",
        "redirect": ["માફ કરશો, સમજાયું નહીં.", "અમે ફક્ત સાડી, દુપટ્ટા અને કાપડ રાખીએ છીએ.", "તૈયાર હો ત્યારે જણાવજો."],
        "not_sold": "માફ કરશો, અમે ફક્ત સાડી, દુપટ્ટા અને કાપડ રાખીએ છીએ.",
        "greeting": "નમસ્તે 🙏",
        "closing": "કોઈ વાંધો નહીં. જ્યારે જોઈએ ત્યારે મેસેજ કરજો 🙏",
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


def turn_text(language, key, variant=0, **values):
    """variant picks one of several phrasings, so repeated replies don't sound canned."""
    t = TURN.get(language, TURN["en"])
    choice = t[key]
    if isinstance(choice, list):
        choice = choice[variant % len(choice)]
    text = choice.format(**values)
    return text[:1].upper() + text[1:]
