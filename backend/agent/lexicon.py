"""Keyword fallback for reading an enquiry when no LLM is available.

Knows English, Hinglish (Hindi in Latin letters), Hindi (Devanagari) and
Gujarati words for colours, patterns, garments, fabrics, borders and work,
plus budgets like "under 2000" / "2000 se kam" / "2000 तक" and quantities
like "50 pcs". Every value it returns is from the fixed vocabulary in
config.yaml.

Limits (the LLM handles these better): no negation ("not red"), no spelling
mistakes beyond the variants listed here.
"""

import re

# Each attribute: list of (value, [words]). Longer phrases are checked first,
# so "zari border" wins over "zari".
WORDS = {
    "main_colour": [
        ("red", ["red", "lal", "laal", "लाल", "લાલ"]),
        ("maroon", ["maroon", "mehroon", "mahroon", "मैरून", "महरून", "મરૂન"]),
        ("pink", ["pink", "gulabi", "rani pink", "rani", "गुलाबी", "रानी", "ગુલાબી"]),
        ("orange", ["orange", "narangi", "kesariya", "kesari", "saffron", "नारंगी", "केसरिया", "કેસરી", "નારંગી"]),
        ("yellow", ["yellow", "peela", "pila", "peeli", "pili", "haldi", "पीला", "पीली", "પીળો", "પીળી", "પીળું"]),
        ("gold", ["gold", "golden", "sunehra", "sunehri", "sunheri", "सुनहरा", "सुनहरी", "गोल्डन", "સોનેરી"]),
        ("green", ["green", "hara", "hari", "hare", "mehndi", "हरा", "हरी", "हरे", "લીલો", "લીલી", "લીલું"]),
        ("navy", ["navy", "navy blue", "नेवी", "નેવી"]),
        ("blue", ["blue", "neela", "nila", "neeli", "nili", "aasmani", "asmani", "नीला", "नीली", "नीले",
                  "आसमानी", "વાદળી", "ભૂરો", "ભૂરી"]),
        ("purple", ["purple", "jamuni", "baingani", "violet", "lavender", "बैंगनी", "जामुनी", "જાંબલી"]),
        ("white", ["white", "safed", "safaid", "सफेद", "सफ़ेद", "સફેદ"]),
        ("cream", ["cream", "off white", "off-white", "ivory", "क्रीम", "ક્રીમ"]),
        ("black", ["black", "kala", "kaala", "kali", "kaali", "काला", "काली", "કાળો", "કાળી", "કાળું"]),
        ("grey", ["grey", "gray", "slate", "sleti", "स्लेटी", "ग्रे", "રાખોડી"]),
        ("brown", ["brown", "bhura", "coffee", "भूरा", "भूरी", "કથ્થઈ"]),
        ("silver", ["silver", "chandi", "चांदी", "सिल्वर", "ચાંદી"]),
        ("multicolour", ["multicolour", "multicolor", "multi colour", "multi color", "rangeen", "colourful",
                         "colorful", "रंगीन", "રંગીન"]),
    ],
    "pattern": [
        ("bandhani", ["bandhani", "bandhej", "bandhni", "bandini", "bandhini", "bandej", "tie dye", "tie-dye",
                      "बांधनी", "बंधेज", "બાંધણી"]),
        ("leheriya", ["leheriya", "lehariya", "laheriya", "lehriya", "लहरिया", "લહેરિયું", "લહેરિયા"]),
        ("floral", ["floral", "flower", "flowers", "phool", "phoolon", "फूल", "फूलों", "ફૂલ"]),
        ("paisley", ["paisley", "keri", "kairi", "mango motif", "कैरी", "કેરી"]),
        ("geometric", ["geometric", "geometrical"]),
        ("checks", ["checks", "checked", "chex", "चेक", "ચેક્સ"]),
        ("stripes", ["stripes", "striped", "stripe", "lining", "dhari", "धारी", "पट्टी", "પટ્ટા"]),
        ("polka dots", ["polka", "polka dots", "dots", "dotted", "बिंदी"]),
        ("patola", ["patola", "पटोला", "પટોળા", "પટોળું"]),
        ("ikat", ["ikat", "ikkat", "pochampally", "इकत", "ઇકત"]),
        ("block print", ["block print", "block printed", "hand block", "bagru", "sanganeri", "dabu", "ajrakh",
                         "ब्लॉक प्रिंट", "બ્લોક પ્રિન્ટ"]),
        ("abstract", ["abstract"]),
        ("plain", ["plain", "sada", "saada", "solid", "सादा", "सादी", "પ્લેન", "સાદી"]),
    ],
    "garment_type": [
        ("saree", ["saree", "sari", "saari", "sarees", "saris", "साड़ी", "साडी", "સાડી"]),
        ("dupatta", ["dupatta", "chunni", "chunri", "chunari", "odhni", "stole", "दुपट्टा", "चुनरी", "ચુંદડી", "દુપટ્ટો"]),
        ("lehenga", ["lehenga", "lehnga", "lehanga", "ghagra", "chaniya choli", "लहंगा", "ચણિયાચોળી", "ચણિયા"]),
        ("dress material", ["dress material", "suit piece", "salwar suit", "suit", "salwar", "सूट", "ડ્રેસ મટીરીયલ"]),
        ("blouse piece", ["blouse piece", "blouse", "ब्लाउज", "બ્લાઉઝ"]),
        ("kurti", ["kurti", "kurta", "कुर्ती", "कुर्ता", "કુર્તી"]),
        ("fabric", ["fabric", "kapda", "kapada", "running material", "कपड़ा", "कपडा", "કાપડ"]),
    ],
    "fabric": [
        ("silk", ["silk", "resham", "reshmi", "रेशम", "रेशमी", "सिल्क", "સિલ્ક", "રેશમ"]),
        ("cotton", ["cotton", "sooti", "suti", "सूती", "कॉटन", "કોટન", "સુતરાઉ"]),
        ("georgette", ["georgette", "jorjet", "जॉर्जेट", "જ્યોર્જેટ"]),
        ("chiffon", ["chiffon", "shifon", "शिफॉन", "શિફોન"]),
        ("crepe", ["crepe", "crape", "क्रेप"]),
        ("net", ["net", "नेट", "નેટ"]),
        ("organza", ["organza", "ऑर्गेंजा"]),
        ("linen", ["linen", "लिनन"]),
        ("rayon", ["rayon", "रेयॉन"]),
        ("polyester", ["polyester", "poly"]),
    ],
    "border": [
        ("zari", ["zari border", "jari border", "जरी बॉर्डर", "ઝરી બોર્ડર"]),
        ("contrast", ["contrast border", "contrast"]),
        ("temple", ["temple border", "temple"]),
        ("embroidered", ["embroidered border"]),
        ("printed", ["printed border"]),
        ("lace", ["lace border", "lace", "laces", "लेस"]),
        ("none", ["no border", "without border", "bina border", "borderless"]),
    ],
    "work_type": [
        ("zari weave", ["zari", "jari", "zari work", "जरी", "ज़री", "ઝરી"]),
        ("embroidery", ["embroidery", "embroidered", "kadhai", "kadai", "thread work", "कढ़ाई", "कढाई", "ભરતકામ"]),
        ("mirror work", ["mirror work", "mirror", "shisha", "sheesha", "abhla", "शीशा", "आभला", "આભલા"]),
        ("sequins", ["sequins", "sequin", "sequence", "sitara", "sitare", "सितारा", "सितारे", "સિતારા"]),
        ("stone work", ["stone work", "stone", "kundan", "स्टोन", "સ્ટોન"]),
        ("hand painted", ["hand painted", "hand-painted", "kalamkari", "painted"]),
        ("print", ["print", "printed", "प्रिंट", "પ્રિન્ટ"]),
    ],
}

# Hindi and Gujarati digits -> 0-9, so "२०००" and "૨૦૦૦" read as 2000
DIGITS = str.maketrans("०१२३४५६७८९૦૧૨૩૪૫૬૭૮૯", "01234567890123456789")

NUMBER = r"(\d+(?:[.,]\d+)?)\s*(k|thousand|hazaar|hazar|हज़ार|हजार|હજાર)?"
CURRENCY = r"(?:₹|rs\.?|inr|rupees?|रुपये|रुपए|રૂપિયા)?\s*"

# "under 2000", "below ₹1,500", "max 2k", "upto 2000", "< 2000"
BUDGET_BEFORE = re.compile(
    r"(?:under|below|less than|within|max|maximum|upto|up to|budget|<)\s*" + CURRENCY + NUMBER,
    re.IGNORECASE,
)
# "2000 se kam", "2000 tak", "2000 ke andar", "2000 से कम", "2000 तक", "2000 સુધી", "2000 થી ઓછું"
BUDGET_AFTER = re.compile(
    CURRENCY + NUMBER + r"\s*(?:rs\.?|rupees?|रुपये|रुपए|રૂપિયા)?\s*"
    r"(?:se kam|tak|ke andar|ke niche|ke neeche|or less|and below|max|से कम|तक|के अंदर|के नीचे|સુધી|થી ઓછું|થી ઓછા)",
    re.IGNORECASE,
)
# "1500-2000", "1500 to 2000" -> the upper number is the budget
BUDGET_RANGE = re.compile(CURRENCY + r"(\d+(?:[.,]\d+)?)\s*(?:-|to|se)\s*" + CURRENCY + NUMBER, re.IGNORECASE)
# "50 pcs", "20 pieces", "10 saree chahiye", "50 पीस"
QUANTITY = re.compile(
    r"(\d+)\s*(?:pcs|pc|pieces|piece|nos|no\.|sets|पीस|नग|પીસ|saree|sarees|sari|साड़ी|સાડી)\b",
    re.IGNORECASE,
)


def _to_number(digits, multiplier):
    value = float(digits.replace(",", ""))
    if multiplier:
        value *= 1000
    return value


def _find_budget(text):
    for pattern in (BUDGET_BEFORE, BUDGET_AFTER):
        m = pattern.search(text)
        if m:
            return _to_number(m.group(1), m.group(2))
    m = BUDGET_RANGE.search(text)
    if m:
        return _to_number(m.group(2), m.group(3))
    return None


def _sensible_budget(value):
    return value if value is not None and value >= MIN_BUDGET else None


def _find_quantity(text):
    m = QUANTITY.search(text)
    return int(m.group(1)) if m else None


def _is_latin(word):
    return all(ord(ch) < 128 for ch in word)


def _positions(text, word):
    """Where a word appears. Latin words must be whole words ("red" not in "covered");
    Hindi/Gujarati words are matched as plain text because their vowel signs break
    the usual whole-word rules."""
    if _is_latin(word):
        return [m.start() for m in re.finditer(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])", text)]
    return [m.start() for m in re.finditer(re.escape(word), text)]


# Common Hindi words typed in English letters. Words that are also English
# ("me", "to") are left out, so "send me blue" stays English.
HINGLISH_WORDS = {
    "chahiye", "chaiye", "hai", "hain", "ka", "ki", "ke", "mein", "wala", "wali", "kya", "dikhao",
    "bhejo", "kitne", "kitna", "accha", "acha", "kuch", "aur", "isme", "ismein", "bhi", "tak", "se",
    "kam", "hoga", "milega", "batao", "dijiye", "bhai", "ji", "yeh", "ye", "woh", "koi", "jaisa",
}


def detect_language(text):
    """'hi' for Devanagari, 'gu' for Gujarati script, 'hinglish' for Hindi in
    English letters, otherwise 'en'."""
    if re.search(r"[઀-૿]", text):
        return "gu"
    if re.search(r"[ऀ-ॿ]", text):
        return "hi"
    words = re.findall(r"[a-z]+", text.lower())
    hits = sum(1 for w in words if w in HINGLISH_WORDS)
    if hits >= 2 or (hits == 1 and len(words) <= 3):
        return "hinglish"
    return "en"


# "net price" / "net rate" is about money, not net fabric
NOT_NET_FABRIC = re.compile(r"\bnet\s+(?:price|rate|amount|total|weight|wt)\b")

# A "budget" below this is almost surely something else (a quantity, a design number)
MIN_BUDGET = 50


def parse(text):
    """Text -> {"attributes": {...}, "max_rate": number|None, "min_quantity": int|None,
    "language": "en"|"hi"|"gu", "matched_words": [...]}"""
    lower = text.lower().translate(DIGITS)
    # Blank out phrases that only look like fabric words (same length keeps positions)
    lower = NOT_NET_FABRIC.sub(lambda m: " " * len(m.group(0)), lower)
    attributes, matched = {}, []
    used = []  # (start, end) of text already claimed, so "zari border" is not also "zari"

    for attr, entries in WORDS.items():
        if attr == "main_colour":
            continue
        found = _match_attribute(lower, entries, used)
        if found:
            value, word = found[0]
            attributes[attr] = value
            matched.append(word)

    # Colours: first one mentioned is the main colour, a different second one is secondary
    colours = _match_attribute(lower, WORDS["main_colour"], used)
    if colours:
        attributes["main_colour"] = colours[0][0]
        matched.append(colours[0][1])
        others = [c for c in colours[1:] if c[0] != colours[0][0]]
        if others:
            attributes["secondary_colour"] = others[0][0]
            matched.append(others[0][1])

    return {
        "attributes": attributes,
        "max_rate": _sensible_budget(_find_budget(lower)),
        "min_quantity": _find_quantity(lower),
        "language": detect_language(text),
        "matched_words": matched,
    }


def _match_attribute(text, entries, used):
    """All (value, word) found for one attribute, in the order they appear in the text.

    Longer phrases are checked first and "use up" their part of the text, so
    "zari border" counts as a zari border and not also as zari work. `used`
    holds the (start, end) spans already taken, shared across attributes."""
    candidates = []
    for value, words in entries:
        for word in words:
            for start in _positions(text, word.lower()):
                candidates.append((start, start + len(word), value, word))
    # Longest phrase first so it claims its text before shorter words inside it
    candidates.sort(key=lambda c: -(c[1] - c[0]))
    found = []
    for start, end, value, word in candidates:
        if any(start < u_end and end > u_start for u_start, u_end in used):
            continue
        used.append((start, end))
        found.append((start, value, word))
    found.sort()
    # Keep the first mention of each value
    result, seen = [], set()
    for _, value, word in found:
        if value not in seen:
            seen.add(value)
            result.append((value, word))
    return result
