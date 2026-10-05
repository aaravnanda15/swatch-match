"""Fixed wording for messages to the buyer, in English, Hindi, Hinglish and Gujarati.

{buyer} and {occasion} are filled in when we know them ("Ramesh ji", "for the
wedding") and dropped cleanly when we don't.
"""

import re

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
        "hello": "Namaste {buyer} 🙏 Here's what we have {occasion}:",
        "hello_no_match": "Namaste {buyer} 🙏 We don't have that exact one right now, but these are close:",
        "rate": "{rate} a {unit}",
        "stock": "{quantity} in stock",
        "only": "only {quantity} left",
        "out": "out of stock right now",
        "ask": "How many pieces would you like?",
        "shade": "(Colours can look a little different on a phone screen.)",
    },
    "hinglish": {
        "hello": "Namaste {buyer} 🙏 Yeh designs abhi available hain {occasion}:",
        "hello_no_match": "Namaste {buyer} 🙏 Bilkul yahi design abhi nahi hai, par yeh kaafi milte-julte hain:",
        "rate": "{rate} per {unit}",
        "stock": "{quantity} stock mein",
        "only": "sirf {quantity} bache hain",
        "out": "abhi stock mein nahi",
        "ask": "Kitne piece chahiye?",
        "shade": "(Photo mein colour thoda alag dikh sakta hai.)",
    },
    "hi": {
        "hello": "नमस्ते {buyer} 🙏 {occasion} ये डिज़ाइन अभी उपलब्ध हैं:",
        "hello_no_match": "नमस्ते {buyer} 🙏 बिल्कुल यही डिज़ाइन अभी नहीं है, पर ये काफ़ी मिलते-जुलते हैं:",
        "rate": "{rate} प्रति {unit}",
        "stock": "{quantity} स्टॉक में",
        "only": "सिर्फ़ {quantity} बचे हैं",
        "out": "अभी स्टॉक में नहीं",
        "ask": "कितने पीस चाहिए?",
        "shade": "(फोटो में रंग थोड़ा अलग दिख सकता है।)",
    },
    "gu": {
        "hello": "નમસ્તે {buyer} 🙏 {occasion} આ ડિઝાઇન હાલ ઉપલબ્ધ છે:",
        "hello_no_match": "નમસ્તે {buyer} 🙏 બરાબર આ જ ડિઝાઇન હાલ નથી, પણ આ ઘણી મળતી આવે છે:",
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


def draft_reply(language, designs, no_match=False, min_quantity=None, buyer="", occasion="", greet=True):
    """designs: list of dicts straight from the database (design_id, name, rate, unit, quantity_available)."""
    t = REPLY.get(language, REPLY["en"])
    hello = t["hello_no_match"] if no_match else t["hello"]
    if not greet:  # a new shortlist in the middle of a chat: no second "Namaste"
        hello = hello.split("🙏 ", 1)[-1]
    lines = [tidy(hello.format(buyer=buyer, occasion=occasion)), ""]
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
        "ask_quantity": ["How many pieces of the {item} would you like?",
                         "How many pieces of the {item} shall I keep for you?",
                         "How many pieces of the {item} do you need {occasion}?"],
        "ask_quantity_short": ["How many pieces would you like?", "How many pieces shall I keep for you?",
                               "How many pieces do you need?"],
        "ask_details": ["What are you looking for today? A photo, the colour or the type (saree, dupatta) is enough.",
                        "Tell me what you have in mind {buyer}. A photo, a colour or the type (saree, dupatta) is enough.",
                        "What can I find for you? Send a photo, or tell me the colour and type (saree, dupatta)."],
        "unit_mismatch": ["{plural} are sold by the {unit}, not by {buyer_unit}. Did you mean {n} {units} of the {item}?",
                          "Just to check {buyer}: {kind} are sold by the {unit}, not by {buyer_unit}. Shall I note {n} {units} of the {item}?",
                          "Our {kind} are sold by the {unit}, not by {buyer_unit}. Do you want {n} {units}?"],
        "confirm_short": ["Did you mean {n} {units} of the {item}?", "Shall I note {n} {units} of the {item}?",
                          "So {n} {units} of the {item}, is that right?"],
        "in_stock": ["Yes, {name} ({design}) is in stock: {available} {units} at {rate} a {unit}. Shall I book {n} {units_n} for you?",
                     "Good news {buyer}, {name} ({design}) is available: {available} {units} at {rate} a {unit}. Shall I book {n} {units_n}?",
                     "{name} ({design}) is ready to go: {available} {units} in stock at {rate} a {unit}. Shall I book {n} {units_n} {occasion}?"],
        "book_short": ["Shall I book {n} {units_n} of {design} for you?", "Shall I go ahead with {n} {units_n} of {design}?",
                       "Shall I confirm {n} {units_n} of {design}?"],
        "short": ["We only have {available} {units} of {design} right now. Would you like all {available}, or shall I show you a few similar designs?",
                  "Sorry {buyer}, {design} has only {available} {units} left. Shall I keep all {available} for you, or show you similar designs?",
                  "Only {available} {units} of {design} are in stock at the moment. Take all {available}, or see a few similar designs?"],
        "take_short": ["Would you like all {available} {units} of {design}, or shall I show you similar designs?",
                       "Shall I keep the {available} {units} of {design}, or show you similar designs?",
                       "All {available} {units} of {design}, or a few similar designs?"],
        "out": ["Sorry, {name} ({design}) is out of stock right now. Shall I show you a few similar designs?",
                "Sorry {buyer}, {name} ({design}) has just sold out. Shall I show you something similar?",
                "{name} ({design}) is out of stock at the moment. Would you like to see a few similar designs?"],
        "similar_short": ["Shall I show you a few designs like {design}?", "Would you like to see something similar to {design}?",
                          "Shall I send a few similar designs?"],
        "confirmed": ["Done! {n} {units} of {name} ({design}) noted. We'll send you the details shortly 🙏",
                      "Thank you {buyer}! {n} {units} of {name} ({design}) are booked {occasion}. We'll send you the details shortly 🙏",
                      "Noted: {n} {units} of {name} ({design}). We'll send you the details shortly 🙏"],
        "stock_line": "• {design} {name}: {available} in stock, {rate} a {unit}",
        "stock_intro": ["Here's the stock right now:", "Here's what's in stock at the moment:", "Stock as of now:"],
        "redirect": ["Sorry, I didn't quite get that.", "We only deal in sarees, dupattas and fabric here.", "Happy to help when you're ready."],
        "not_sold": ["Sorry, we only deal in sarees, dupattas and fabric.",
                     "Sorry {buyer}, we only deal in sarees, dupattas and fabric.",
                     "We only deal in sarees, dupattas and fabric, so I can't help with that one."],
        "greeting": ["Namaste {buyer} 🙏", "Namaste {buyer}, good to hear from you 🙏", "Hello {buyer} 🙏"],
        "welcome_back": ["Welcome back {buyer}! Still keen on the {item}?", "Good to see you again {buyer}. Shall we pick up the {item}?",
                         "Welcome back {buyer}! We were talking about the {item}."],
        "closing": ["No problem. Message us whenever you're ready, we're happy to help 🙏",
                    "That's alright {buyer}. Message us whenever you're ready 🙏",
                    "No rush at all. Message us whenever you're ready and we'll take it from there 🙏"],
        "good_choice": ["Good choice {buyer}!", "Lovely pick!", "Sure {buyer}."],
        "fabric_answer": ["{name} ({design}) is {fabric}, as per our catalogue.",
                          "Our catalogue lists {name} ({design}) as {fabric}.", "{name} ({design}) is a {fabric} piece."],
        "staff_confirm": ["Good question {buyer}. Let me check with the owner and get back to you shortly.",
                          "I'll confirm that with the owner and reply shortly {buyer}.",
                          "Let me check that for you and come back shortly."],
        "no_more": ["Sorry, nothing else like this in stock right now.", "Sorry {buyer}, that's all we have like this at the moment.",
                    "Nothing else like this is in stock right now, sorry."],
    },
    "hinglish": {
        "ask_quantity": ["{item} ke kitne piece chahiye?", "{item} ke kitne piece rakh doon aapke liye?",
                         "{occasion} {item} ke kitne piece chahiye?"],
        "ask_quantity_short": ["Kitne piece chahiye?", "Kitne piece rakh doon?", "Aapko kitne piece chahiye?"],
        "ask_details": ["Aapko kya chahiye? Photo, colour ya type (saree, dupatta) bata dijiye.",
                        "Bataiye {buyer}, kya dhoondh rahe hain? Photo, colour ya type (saree, dupatta) kaafi hai.",
                        "Kya dikhaun aapko? Photo bhejiye, ya colour aur type (saree, dupatta) bata dijiye."],
        "unit_mismatch": ["{plural} {unit} mein milti hai, {buyer_unit} mein nahi. Kya aapko {item} ke {n} {units} chahiye?",
                          "Ek baat {buyer}: {kind} {unit} mein milti hain, {buyer_unit} mein nahi. {item} ke {n} {units} likh doon?",
                          "Hum {kind} {unit} mein dete hain, {buyer_unit} mein nahi. {n} {units} chahiye?"],
        "confirm_short": ["Kya aapko {item} ke {n} {units} chahiye?", "{item} ke {n} {units} likh doon?",
                          "Toh {n} {units} {item}, sahi hai?"],
        "in_stock": ["Haan ji, {name} ({design}) available hai: {available} {units}, {rate} per {unit}. {n} {units_n} book kar dein?",
                     "Achhi khabar {buyer}, {name} ({design}) stock mein hai: {available} {units}, {rate} per {unit}. {n} {units_n} book kar doon?",
                     "{name} ({design}) ready hai: {available} {units} stock mein, {rate} per {unit}. {n} {units_n} book karein?"],
        "book_short": ["{design} ke {n} {units_n} book kar dein?", "{design} ke {n} {units_n} pakke kar doon?",
                       "{n} {units_n} {design} confirm karein?"],
        "short": ["{design} ke abhi sirf {available} {units} hain. Saare {available} le lenge, ya milte-julte design dikhayein?",
                  "Maaf kijiye {buyer}, {design} ke sirf {available} {units} bache hain. Saare {available} rakh doon, ya milte-julte design dikhaun?",
                  "{design} abhi sirf {available} {units} stock mein hai. Saare {available} lenge, ya aur design dekhenge?"],
        "take_short": ["{design} ke saare {available} {units} le lenge, ya milte-julte design dikhayein?",
                       "{available} {units} {design} rakh doon, ya milte-julte design dikhaun?",
                       "Saare {available} {units} lenge, ya aur design dekhenge?"],
        "out": ["Maaf kijiye, {name} ({design}) abhi stock mein nahi hai. Milte-julte design dikhayein?",
                "Maaf kijiye {buyer}, {name} ({design}) abhi khatam ho gaya hai. Kuch milta-julta dikhaun?",
                "{name} ({design}) abhi stock mein nahi hai. Milte-julte design dekhenge?"],
        "similar_short": ["{design} jaise kuch design dikhayein?", "Milte-julte design dikhaun?", "Kuch milta-julta dekhenge?"],
        "confirmed": ["Ho gaya! {name} ({design}) ke {n} {units} note kar liye. Details thodi der mein bhejte hain 🙏",
                      "Dhanyavaad {buyer}! {name} ({design}) ke {n} {units} book ho gaye. Details thodi der mein bhejte hain 🙏",
                      "Note kar liya: {name} ({design}) ke {n} {units}. Details jaldi bhejte hain 🙏"],
        "stock_line": "• {design} {name}: {available} stock mein, {rate} per {unit}",
        "stock_intro": ["Abhi ka stock:", "Abhi stock mein yeh hai:", "Stock ki details:"],
        "redirect": ["Maaf kijiye, samajh nahi aaya.", "Hum sirf saree, dupatta aur kapda rakhte hain.", "Jab ready ho, bata dijiye."],
        "not_sold": ["Maaf kijiye, hum sirf saree, dupatta aur kapda rakhte hain.",
                     "Maaf kijiye {buyer}, hum sirf saree, dupatta aur kapda rakhte hain.",
                     "Yeh hamare paas nahi milega, hum sirf saree, dupatta aur kapda rakhte hain."],
        "greeting": ["Namaste {buyer} 🙏", "Namaste {buyer}, kahiye 🙏", "Ji {buyer}, namaste 🙏"],
        "welcome_back": ["Welcome back {buyer}! {item} ka order aage badhayein?", "Phir se swagat hai {buyer}! {item} ki baat chal rahi thi.",
                         "Aaiye {buyer}! {item} ka kya socha?"],
        "closing": ["Koi baat nahi. Jab bhi chahiye, message kar dijiye 🙏", "Theek hai {buyer}. Jab ready hon, message kar dijiye 🙏",
                    "Koi jaldi nahi. Jab bhi chahiye, bata dijiye 🙏"],
        "good_choice": ["Badhiya choice {buyer}!", "Achha design chuna!", "Ji {buyer}."],
        "fabric_answer": ["{name} ({design}) ka fabric {fabric} hai, catalogue ke hisaab se.",
                          "Catalogue mein {name} ({design}) {fabric} likha hai.", "{name} ({design}) {fabric} ka hai."],
        "staff_confirm": ["Achha sawaal {buyer}. Owner se confirm karke thodi der mein batate hain.",
                          "Yeh owner se pakka karke thodi der mein batate hain {buyer}.",
                          "Iski jaankari pakki karke jaldi batate hain."],
        "no_more": ["Maaf kijiye, abhi aise aur design stock mein nahi hain.",
                    "Maaf kijiye {buyer}, is tarah ke itne hi design abhi hain.",
                    "Abhi aise aur design stock mein nahi hain, maaf kijiye."],
    },
    "hi": {
        "ask_quantity": ["{item} के कितने पीस चाहिए?", "{item} के कितने पीस आपके लिए रख दूँ?", "{occasion} {item} के कितने पीस चाहिए?"],
        "ask_quantity_short": ["कितने पीस चाहिए?", "कितने पीस रख दूँ?", "आपको कितने पीस चाहिए?"],
        "ask_details": ["आपको क्या चाहिए? फोटो, रंग या प्रकार (साड़ी, दुपट्टा) बता दीजिए।",
                        "बताइए {buyer}, क्या ढूँढ रहे हैं? फोटो, रंग या प्रकार (साड़ी, दुपट्टा) काफ़ी है।",
                        "क्या दिखाऊँ? फोटो भेजिए, या रंग और प्रकार (साड़ी, दुपट्टा) बता दीजिए।"],
        "unit_mismatch": ["{plural} {unit} में मिलती है, {buyer_unit} में नहीं। क्या आपको {item} के {n} {units} चाहिए?",
                          "एक बात {buyer}: {kind} {unit} में मिलती हैं, {buyer_unit} में नहीं। {item} के {n} {units} लिख दूँ?",
                          "हम {kind} {unit} में देते हैं, {buyer_unit} में नहीं। {n} {units} चाहिए?"],
        "confirm_short": ["क्या आपको {item} के {n} {units} चाहिए?", "{item} के {n} {units} लिख दूँ?", "तो {n} {units} {item}, सही है?"],
        "in_stock": ["जी हाँ, {name} ({design}) उपलब्ध है: {available} {units}, {rate} प्रति {unit}। {n} {units_n} बुक कर दें?",
                     "अच्छी ख़बर {buyer}, {name} ({design}) स्टॉक में है: {available} {units}, {rate} प्रति {unit}। {n} {units_n} बुक कर दूँ?",
                     "{name} ({design}) तैयार है: {available} {units} स्टॉक में, {rate} प्रति {unit}। {occasion} {n} {units_n} बुक करें?"],
        "book_short": ["{design} के {n} {units_n} बुक कर दें?", "{design} के {n} {units_n} पक्के कर दूँ?", "{n} {units_n} {design} कन्फ़र्म करें?"],
        "short": ["{design} के अभी सिर्फ़ {available} {units} हैं। सारे {available} लेंगे, या मिलते-जुलते डिज़ाइन दिखाएँ?",
                  "माफ़ कीजिए {buyer}, {design} के सिर्फ़ {available} {units} बचे हैं। सारे {available} रख दूँ, या मिलते-जुलते डिज़ाइन दिखाऊँ?",
                  "{design} अभी सिर्फ़ {available} {units} स्टॉक में है। सारे {available} लेंगे, या और डिज़ाइन देखेंगे?"],
        "take_short": ["{design} के सारे {available} {units} लेंगे, या मिलते-जुलते डिज़ाइन दिखाएँ?",
                       "{available} {units} {design} रख दूँ, या मिलते-जुलते डिज़ाइन दिखाऊँ?",
                       "सारे {available} {units} लेंगे, या और डिज़ाइन देखेंगे?"],
        "out": ["माफ़ कीजिए, {name} ({design}) अभी स्टॉक में नहीं है। मिलते-जुलते डिज़ाइन दिखाएँ?",
                "माफ़ कीजिए {buyer}, {name} ({design}) अभी ख़त्म हो गया है। कुछ मिलता-जुलता दिखाऊँ?",
                "{name} ({design}) अभी स्टॉक में नहीं है। मिलते-जुलते डिज़ाइन देखेंगे?"],
        "similar_short": ["{design} जैसे कुछ डिज़ाइन दिखाएँ?", "मिलते-जुलते डिज़ाइन दिखाऊँ?", "कुछ मिलता-जुलता देखेंगे?"],
        "confirmed": ["हो गया! {name} ({design}) के {n} {units} नोट कर लिए। जानकारी थोड़ी देर में भेजते हैं 🙏",
                      "धन्यवाद {buyer}! {name} ({design}) के {n} {units} बुक हो गए। जानकारी थोड़ी देर में भेजते हैं 🙏",
                      "नोट कर लिया: {name} ({design}) के {n} {units}। जानकारी जल्दी भेजते हैं 🙏"],
        "stock_line": "• {design} {name}: {available} स्टॉक में, {rate} प्रति {unit}",
        "stock_intro": ["अभी का स्टॉक:", "अभी स्टॉक में यह है:", "स्टॉक की जानकारी:"],
        "redirect": ["माफ़ कीजिए, समझ नहीं आया।", "हम सिर्फ़ साड़ी, दुपट्टा और कपड़ा रखते हैं।", "जब तैयार हों, बता दीजिए।"],
        "not_sold": ["माफ़ कीजिए, हम सिर्फ़ साड़ी, दुपट्टा और कपड़ा रखते हैं।",
                     "माफ़ कीजिए {buyer}, हम सिर्फ़ साड़ी, दुपट्टा और कपड़ा रखते हैं।",
                     "यह हमारे पास नहीं मिलेगा, हम सिर्फ़ साड़ी, दुपट्टा और कपड़ा रखते हैं।"],
        "greeting": ["नमस्ते {buyer} 🙏", "नमस्ते {buyer}, कहिए 🙏", "जी {buyer}, नमस्ते 🙏"],
        "welcome_back": ["फिर से स्वागत है {buyer}! क्या अभी भी {item} चाहिए?", "आइए {buyer}! {item} की बात चल रही थी।",
                         "स्वागत है {buyer}! {item} के बारे में क्या सोचा?"],
        "closing": ["कोई बात नहीं। जब भी चाहिए, मैसेज कर दीजिए 🙏", "ठीक है {buyer}। जब तैयार हों, मैसेज कर दीजिए 🙏",
                    "कोई जल्दी नहीं। जब भी चाहिए, बता दीजिए 🙏"],
        "good_choice": ["बढ़िया पसंद {buyer}!", "अच्छा डिज़ाइन चुना!", "जी {buyer}।"],
        "fabric_answer": ["{name} ({design}) का कपड़ा {fabric} है, हमारे कैटलॉग के हिसाब से।",
                          "कैटलॉग में {name} ({design}) {fabric} लिखा है।", "{name} ({design}) {fabric} का है।"],
        "staff_confirm": ["अच्छा सवाल {buyer}। मालिक से पूछकर थोड़ी देर में बताते हैं।",
                          "यह पक्का करके थोड़ी देर में बताते हैं {buyer}।", "इसकी जानकारी पक्की करके जल्दी बताते हैं।"],
        "no_more": ["माफ़ कीजिए, अभी ऐसे और डिज़ाइन स्टॉक में नहीं हैं।", "माफ़ कीजिए {buyer}, इस तरह के इतने ही डिज़ाइन अभी हैं।",
                    "अभी ऐसे और डिज़ाइन स्टॉक में नहीं हैं, माफ़ कीजिए।"],
    },
    "gu": {
        "ask_quantity": ["{item} ના કેટલા પીસ જોઈએ?", "{item} ના કેટલા પીસ તમારા માટે રાખું?", "{occasion} {item} ના કેટલા પીસ જોઈએ?"],
        "ask_quantity_short": ["કેટલા પીસ જોઈએ?", "કેટલા પીસ રાખું?", "તમને કેટલા પીસ જોઈએ?"],
        "ask_details": ["તમને શું જોઈએ છે? ફોટો, રંગ કે પ્રકાર (સાડી, દુપટ્ટો) જણાવો.",
                        "કહો {buyer}, શું શોધો છો? ફોટો, રંગ કે પ્રકાર (સાડી, દુપટ્ટો) પૂરતું છે.",
                        "શું બતાવું? ફોટો મોકલો, અથવા રંગ અને પ્રકાર (સાડી, દુપટ્ટો) જણાવો."],
        "unit_mismatch": ["{plural} {unit}માં મળે છે, {buyer_unit}માં નહીં. શું તમને {item} ના {n} {units} જોઈએ છે?",
                          "એક વાત {buyer}: {kind} {unit}માં મળે છે, {buyer_unit}માં નહીં. {item} ના {n} {units} લખી દઉં?",
                          "અમે {kind} {unit}માં આપીએ છીએ, {buyer_unit}માં નહીં. {n} {units} જોઈએ છે?"],
        "confirm_short": ["શું તમને {item} ના {n} {units} જોઈએ છે?", "{item} ના {n} {units} લખી દઉં?", "તો {n} {units} {item}, બરાબર?"],
        "in_stock": ["હા, {name} ({design}) ઉપલબ્ધ છે: {available} {units}, {rate} પ્રતિ {unit}. {n} {units_n} બુક કરીએ?",
                     "સારા સમાચાર {buyer}, {name} ({design}) સ્ટોકમાં છે: {available} {units}, {rate} પ્રતિ {unit}. {n} {units_n} બુક કરી દઉં?",
                     "{name} ({design}) તૈયાર છે: {available} {units} સ્ટોકમાં, {rate} પ્રતિ {unit}. {occasion} {n} {units_n} બુક કરીએ?"],
        "book_short": ["{design} ના {n} {units_n} બુક કરીએ?", "{design} ના {n} {units_n} પાક્કા કરી દઉં?", "{n} {units_n} {design} કન્ફર્મ કરીએ?"],
        "short": ["{design} ના હાલ ફક્ત {available} {units} છે. બધા {available} લેશો, કે મળતી ડિઝાઇન બતાવીએ?",
                  "માફ કરશો {buyer}, {design} ના ફક્ત {available} {units} બાકી છે. બધા {available} રાખી દઉં, કે મળતી ડિઝાઇન બતાવું?",
                  "{design} હાલ ફક્ત {available} {units} સ્ટોકમાં છે. બધા {available} લેશો, કે બીજી ડિઝાઇન જોશો?"],
        "take_short": ["{design} ના બધા {available} {units} લેશો, કે મળતી ડિઝાઇન બતાવીએ?",
                       "{available} {units} {design} રાખી દઉં, કે મળતી ડિઝાઇન બતાવું?",
                       "બધા {available} {units} લેશો, કે બીજી ડિઝાઇન જોશો?"],
        "out": ["માફ કરશો, {name} ({design}) હાલ સ્ટોકમાં નથી. મળતી ડિઝાઇન બતાવીએ?",
                "માફ કરશો {buyer}, {name} ({design}) હાલ ખતમ થઈ ગઈ છે. કંઈક મળતું બતાવું?",
                "{name} ({design}) હાલ સ્ટોકમાં નથી. મળતી ડિઝાઇન જોશો?"],
        "similar_short": ["{design} જેવી થોડી ડિઝાઇન બતાવીએ?", "મળતી ડિઝાઇન બતાવું?", "કંઈક મળતું જોશો?"],
        "confirmed": ["થઈ ગયું! {name} ({design}) ના {n} {units} નોંધી લીધા. વિગતો થોડી વારમાં મોકલીએ છીએ 🙏",
                      "આભાર {buyer}! {name} ({design}) ના {n} {units} બુક થઈ ગયા. વિગતો થોડી વારમાં મોકલીએ છીએ 🙏",
                      "નોંધી લીધું: {name} ({design}) ના {n} {units}. વિગતો જલ્દી મોકલીએ છીએ 🙏"],
        "stock_line": "• {design} {name}: {available} સ્ટોકમાં, {rate} પ્રતિ {unit}",
        "stock_intro": ["હાલનો સ્ટોક:", "હાલ સ્ટોકમાં આ છે:", "સ્ટોકની વિગત:"],
        "redirect": ["માફ કરશો, સમજાયું નહીં.", "અમે ફક્ત સાડી, દુપટ્ટા અને કાપડ રાખીએ છીએ.", "તૈયાર હો ત્યારે જણાવજો."],
        "not_sold": ["માફ કરશો, અમે ફક્ત સાડી, દુપટ્ટા અને કાપડ રાખીએ છીએ.",
                     "માફ કરશો {buyer}, અમે ફક્ત સાડી, દુપટ્ટા અને કાપડ રાખીએ છીએ.",
                     "એ અમારી પાસે નહીં મળે, અમે ફક્ત સાડી, દુપટ્ટા અને કાપડ રાખીએ છીએ."],
        "greeting": ["નમસ્તે {buyer} 🙏", "નમસ્તે {buyer}, કેમ છો? 🙏", "નમસ્તે {buyer}, બોલો 🙏"],
        "welcome_back": ["ફરી સ્વાગત છે {buyer}! હજુ પણ {item} જોઈએ છે?", "આવો {buyer}! {item} ની વાત ચાલતી હતી.",
                         "સ્વાગત છે {buyer}! {item} વિશે શું વિચાર્યું?"],
        "closing": ["કોઈ વાંધો નહીં. જ્યારે જોઈએ ત્યારે મેસેજ કરજો 🙏", "બરાબર {buyer}. તૈયાર હો ત્યારે મેસેજ કરજો 🙏",
                    "કોઈ ઉતાવળ નથી. જ્યારે જોઈએ ત્યારે જણાવજો 🙏"],
        "good_choice": ["સરસ પસંદગી {buyer}!", "સારી ડિઝાઇન પસંદ કરી!", "જી {buyer}."],
        "fabric_answer": ["{name} ({design}) નું કાપડ {fabric} છે, અમારા કેટલોગ મુજબ.",
                          "કેટલોગમાં {name} ({design}) {fabric} લખેલું છે.", "{name} ({design}) {fabric} નું છે."],
        "staff_confirm": ["સારો પ્રશ્ન {buyer}. માલિક સાથે વાત કરીને થોડી વારમાં જણાવીએ છીએ.",
                          "આ પાક્કું કરીને થોડી વારમાં જણાવીએ {buyer}.", "આની માહિતી પાક્કી કરીને જલ્દી જણાવીએ છીએ."],
        "no_more": ["માફ કરશો, હાલ આવી બીજી ડિઝાઇન સ્ટોકમાં નથી.", "માફ કરશો {buyer}, આ પ્રકારની આટલી જ ડિઝાઇન હાલ છે.",
                    "હાલ આવી બીજી ડિઝાઇન સ્ટોકમાં નથી, માફ કરશો."],
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
    text = tidy(choice.format(**{"buyer": "", "occasion": "", **values}))
    return text[:1].upper() + text[1:]


def variant_count(language, key):
    choice = TURN.get(language, TURN["en"])[key]
    return len(choice) if isinstance(choice, list) else 1


def tidy(text):
    """Close the gaps an empty {buyer} or {occasion} leaves ("Namaste  🙏", "Sorry , we")."""
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r" +([,.!?:।])", r"\1", text)
    text = re.sub(r"[,:]([.!?])", r"\1", text)
    text = re.sub(r"([.!?] +)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)
    return re.sub(r"(?m)^[ ,]+", "", text).strip()


# How we address the buyer: their first name and "ji". Shop words are skipped,
# so "Ramesh Textiles" is "Ramesh ji"; a name we can't use leaves {buyer} empty.
HONORIFIC = {"en": "ji", "hinglish": "ji", "hi": "जी", "gu": "જી"}
NOT_A_NAME = {"buyer", "customer", "test", "textile", "textiles", "fabric", "fabrics", "saree", "sarees", "sari",
              "centre", "center", "traders", "trading", "trader", "boutique", "store", "stores", "shop", "collection",
              "collections", "creation", "creations", "fashion", "fashions", "emporium", "enterprises", "mart",
              "house", "and", "the", "mr", "mrs", "ms", "dr", "shree", "shri", "sri"}


def first_name(profile_name):
    for word in re.findall(r"[^\W\d_]+", profile_name or ""):
        if len(word) > 1 and word.lower() not in NOT_A_NAME:
            return word[:1].upper() + word[1:]
    return None


def address(language, name):
    return f"{name} {HONORIFIC.get(language, 'ji')}" if name else ""


OCCASION_WORDS = {
    "en": {"wedding": "for the wedding", "festival": "for the festival", "party": "for the function"},
    "hinglish": {"wedding": "shaadi ke liye", "festival": "tyohar ke liye", "party": "function ke liye"},
    "hi": {"wedding": "शादी के लिए", "festival": "त्योहार के लिए", "party": "फ़ंक्शन के लिए"},
    "gu": {"wedding": "લગ્ન માટે", "festival": "તહેવાર માટે", "party": "પ્રસંગ માટે"},
}


def occasion_words(language, occasion):
    return OCCASION_WORDS.get(language, OCCASION_WORDS["en"]).get(occasion, "")


EMOJI = r"[\U0001F300-\U0001FAFF\u2600-\u27BF]"


def no_emoji(text):
    """For buyers who write formally: "Namaste 🙏 Here's" becomes "Namaste. Here's"."""
    text = re.sub(rf" *{EMOJI}+(?= +\S)", ".", text)
    text = tidy(re.sub(EMOJI, "", text))
    return text + "." if text[-1:].isalpha() else text
