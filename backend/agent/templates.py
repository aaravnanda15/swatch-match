"""Fixed wording for messages to the buyer, in English, Hindi, Hinglish and
Gujarati. Used when the LLM is off, and ALWAYS for any line with a stock
number or a rate, so numbers can never be made up.
"""

# ---------- clarifying question (one question only) ----------

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
    """One polite question asking for the most useful missing details."""
    texts = CLARIFY.get(language, CLARIFY["en"])
    known = [v for v in attributes.values() if v not in ("none", "other", "unknown")]
    if known:
        return texts["known"].format(known=" ".join(known))
    return texts["nothing"]
