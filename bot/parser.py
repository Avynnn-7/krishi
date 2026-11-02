import re
import unicodedata

CROPS = {
    "wheat": {
        "1", "wheat", "gehun", "gehu", "gehoo", "gehoon", "gahu",
        "गेहूं", "गेहूँ", "गेहुं", "गेहू",
    },
    "sugarcane": {
        "2", "sugarcane", "ganna", "ganne", "गन्ना", "गन्ने", "cane",
    },
    "rice": {
        "3", "rice", "dhan", "dhaan", "धान", "chawal", "chaawal", "paddy",
    },
    "maize": {
        "4", "maize", "makka", "makkai", "makki", "मक्का", "मक्की", "corn",
    },
}


def normalize(text: str) -> str:
    return "".join(
        str(unicodedata.decimal(c)) if c.isdecimal() else c for c in text.strip().lower()
    )


def parse_crop(text: str) -> str:
    normalized = normalize(text)
    for crop, synonyms in CROPS.items():
        if normalized in synonyms:
            return crop
    raise ValueError("फसल का नंबर 1–4 भेजें, जैसे 1 / गेहूं / wheat।")


def parse_number(text: str) -> float:
    normalized = normalize(text)
    match = re.fullmatch(
        r"(?:₹|rs\.?\s*)?\s*(\d+(?:\.\d{1,2})?)\s*(?:rs\.?|rupees|रुपये)?", normalized
    )
    if not match:
        raise ValueError("केवल धनात्मक अंक भेजें, जैसे 2000।")
    return float(match.group(1))


def parse_soil(text: str) -> tuple[float, float, float]:
    parts = re.split(r"[,/\s]+", normalize(text))
    if len(parts) != 3 or not all(re.fullmatch(r"\d+(?:\.\d+)?", p) for p in parts):
        raise ValueError("N,P,K kg/ha में भेजें, जैसे 180,45,220।")
    n, p, k = map(float, parts)
    if n > 2000 or p > 2000 or k > 3000:
        raise ValueError("मिट्टी के मान सीमा से बाहर हैं; कार्ड की इकाई जाँचें।")
    return n, p, k


def parse_yes_no(text: str) -> bool:
    """Parse yes/no in Hindi, Hinglish, and English.

    Accounts for common voice-transcription romanisations:
    han, haa, haan, ji, ji haan, nahin, nahi, na, etc.
    """
    value = normalize(text)
    YES = {
        "1", "yes", "yeah", "yep", "ok", "okay",
        "ha", "haa", "han", "haan", "hanji", "ji", "ji haan",
        "jee", "jee haan", "bilkul", "zaroor", "zarur",
        "हाँ", "हां", "हाँजी", "जी", "जी हाँ",
        "बिल्कुल", "ज़रूर",
    }
    NO = {
        "2", "no", "nope",
        "nahi", "nahin", "nai", "na", "mat", "bilkul nahi",
        "nahin ji", "nahi ji",
        "नहीं", "नही", "ना", "नहीं जी", "मत",
    }
    if value in YES:
        return True
    if value in NO:
        return False
    raise ValueError("1 (हाँ) या 2 (नहीं) भेजें।")


UK_BIGHA_M2 = 632.29

HINDI_NUMBER_WORDS = {
    "आधा": 0.5,
    "aadha": 0.5,
    "half": 0.5,
    "एक": 1.0,
    "ek": 1.0,
    "one": 1.0,
    "डेढ़": 1.5,
    "dedh": 1.5,
    "दो": 2.0,
    "do": 2.0,
    "two": 2.0,
    "ढाई": 2.5,
    "ढ़ाई": 2.5,
    "dhai": 2.5,
    "तीन": 3.0,
    "teen": 3.0,
    "three": 3.0,
    "चार": 4.0,
    "char": 4.0,
    "four": 4.0,
    "पाँच": 5.0,
    "पांच": 5.0,
    "panch": 5.0,
    "paanch": 5.0,
    "five": 5.0,
    "छह": 6.0,
    "छः": 6.0,
    "chhah": 6.0,
    "six": 6.0,
    "सात": 7.0,
    "saat": 7.0,
    "seven": 7.0,
    "आठ": 8.0,
    "aath": 8.0,
    "eight": 8.0,
    "नौ": 9.0,
    "nau": 9.0,
    "nine": 9.0,
    "दस": 10.0,
    "das": 10.0,
    "ten": 10.0,
    "बारह": 12.0,
    "barah": 12.0,
    "पंद्रह": 15.0,
    "pandrah": 15.0,
    "बीस": 20.0,
    "bees": 20.0,
    "पच्चीस": 25.0,
    "pachees": 25.0,
    "तीस": 30.0,
    "tees": 30.0,
    "चालीस": 40.0,
    "chalis": 40.0,
    "पचास": 50.0,
    "pachas": 50.0,
    "gyarah": 11.0,
    "ग्यारह": 11.0,
    "eleven": 11.0,
    "twelve": 12.0,
    "बाहर": 12.0,
    "terah": 13.0,
    "तेरह": 13.0,
    "thirteen": 13.0,
    "chaudah": 14.0,
    "चौदह": 14.0,
    "fourteen": 14.0,
    "fifteen": 15.0,
    "पन्द्रह": 15.0,
    "solah": 16.0,
    "sixteen": 16.0,
    "satrah": 17.0,
    "seventeen": 17.0,
    "athaarah": 18.0,
    "eighteen": 18.0,
    "unees": 19.0,
    "nineteen": 19.0,
    "twenty": 20.0,
    "beees": 20.0,
    "pachis": 25.0,
    "twenty five": 25.0,
    "thirties": 30.0,
    "thirty": 30.0,
    "chalees": 40.0,
    "forty": 40.0,
    "fifty": 50.0,
    "pachaas": 50.0,
    "saath": 60.0,
    "sixty": 60.0,
    "साठ": 60.0,
    "sattar": 70.0,
    "seventy": 70.0,
    "सत्तर": 70.0,
    "assi": 80.0,
    "eighty": 80.0,
    "अस्सी": 80.0,
    "nabbe": 90.0,
    "ninety": 90.0,
    "नब्बे": 90.0,
    "sau": 100.0,
    "hundred": 100.0,
    "सौ": 100.0,
}

BLOCK_SYNONYMS = {
    "Roorkee": (
        "roorkee", "rurki", "rurkey", "roorkee", "roorki", "rorki",
        "रुड़की", "रूरकी", "रुडकी", "रूड़की",
    ),
    "Bhagwanpur": (
        "bhagwanpur", "bhagvanpur", "bhagwan pur",
        "भगवानपुर", "भगवान पुर",
    ),
    "Laksar": (
        "laksar", "laxar", "lakser",
        "लक्सर", "लकसर",
    ),
    "Narsan": (
        "narsan", "narsen", "gurukul narsan", "gurukul",
        "नारसन", "नरसन", "गुरुकुल नारसन", "गुरुकुल",
    ),
    "Bahadrabad": (
        "bahadrabad", "bahadarabad", "bahadarabaad", "bahadraabaad",
        "बहादराबाद",
    ),
    "Khanpur": (
        "khanpur", "khanpoor", "khan pur",
        "खानपुर", "खान पुर",
    ),
}


def parse_spoken_budget(text: str) -> float | None:
    """Parse spoken Hindi/Hinglish/English budget phrases such as 'दो हज़ार', '2500 रुपये', 'तीन हजार'."""
    norm = normalize(text)
    try:
        return parse_number(norm)
    except ValueError:
        pass
    # Look for explicit हजार / हज़ार / thousand / सौ
    for word, mult in sorted(HINDI_NUMBER_WORDS.items(), key=lambda x: -len(x[0])):
        if re.search(rf"(?:^|\s){re.escape(word)}\s*(?:हज़ार|हजार|hazar|hazaar|thousand)", norm):
            return mult * 1000.0
        if re.search(rf"(?:^|\s){re.escape(word)}\s*(?:सौ|sau|hundred)", norm):
            return mult * 100.0
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:हज़ार|हजार|hazar|hazaar|thousand)", norm)
    if match:
        return float(match.group(1)) * 1000.0
    match = re.search(
        r"(?:बजट|budget|रुपये|रुपए|rs\.?|₹)\s*(\d{3,7}(?:\.\d{1,2})?)|(\d{3,7}(?:\.\d{1,2})?)\s*(?:रुपये|रुपए|rupees|rs\.?|₹)",
        norm,
    )
    if match:
        return float(match.group(1) or match.group(2))
    return None


def parse_area(text: str) -> dict:
    """Accept '0.5', '0.5 ha', '2 bigha', '1.5 acre', or spoken 'पाँच बीघा', 'दो एकड़'."""
    normalized = (
        normalize(text)
        .replace("बीघे", "bigha")
        .replace("बीघा", "bigha")
        .replace("एकड़", "acre")
        .replace("हेक्टेयर", "ha")
    )
    match = re.fullmatch(r"(\d+(?:\.\d{1,3})?)\s*(ha|hectare|acre|acres|bigha|bighe)?", normalized)
    if not match:
        # Check spoken Hindi number + explicit unit (e.g. 'पाँच बीघा', 'दो एकड़')
        spoken_val = None
        spoken_unit = None
        for word, val in sorted(HINDI_NUMBER_WORDS.items(), key=lambda x: -len(x[0])):
            m = re.fullmatch(
                rf"{re.escape(word)}\s+(ha|hectare|acre|acres|bigha|bighe)", normalized
            )
            if m:
                spoken_val = val
                spoken_unit = m.group(1)
                break
        if spoken_val is None or spoken_unit is None:
            raise ValueError("क्षेत्र ऐसे भेजें: 5 bigha / 1 acre / 0.5 ha (या बोलें 'पाँच बीघा')।")
        value, unit = spoken_val, spoken_unit
    else:
        value, unit = float(match.group(1)), match.group(2) or "ha"
    if unit.startswith("bigh"):
        area = {"area": value, "area_unit": "bigha", "bigha_m2": UK_BIGHA_M2}
        hectares = value * UK_BIGHA_M2 / 10000
    elif unit.startswith("acre"):
        area = {"area": value, "area_unit": "acre"}
        hectares = value * 0.40468564224
    else:
        area = {"area": value, "area_unit": "ha"}
        hectares = value
    if not 0 < hectares <= 100:
        raise ValueError("क्षेत्र 0 से अधिक और 100 हेक्टेयर तक होना चाहिए।")
    return area


def decipher_voice_utterance(text: str, blocks_data: dict | None = None) -> dict:
    """Extract structured farmer entities (block, village, crop, area, budget, NPK) from natural speech."""
    norm = normalize(text)
    extracted: dict = {"raw": text.strip()}

    # 1. Detect Block
    for block_name, syns in BLOCK_SYNONYMS.items():
        if any(s in norm for s in syns):
            extracted["block"] = block_name
            break

    # 2. Detect Village from Haridwar–Roorkee gazetteer (prefer distinct village names over block town homonyms)
    if blocks_data and "blocks" in blocks_data:
        candidates = []
        for b_name, b_info in blocks_data["blocks"].items():
            for v in b_info.get("villages", []):
                if v["name"].lower() in norm or v["hi"].lower() in norm:
                    is_block_homonym = v["name"].lower() == b_name.lower()
                    candidates.append((is_block_homonym, b_name, v))
        if candidates:
            candidates.sort(key=lambda item: item[0])
            _, b_name, v = candidates[0]
            extracted["village"] = v["name"]
            extracted["village_hi"] = v["hi"]
            extracted.setdefault("block", b_name)
            extracted["latitude"] = v["lat"]
            extracted["longitude"] = v["lon"]
            extracted["texture"] = v.get("texture", "sandy-loam")
    if "village" not in extracted:
        v_match = re.search(
            r"(?:गाँव|गांव|village)\s+([a-zA-Z\u0900-\u097f]{2,30})", text.strip(), re.I
        )
        if v_match:
            extracted["village"] = v_match.group(1).strip()

    # 3. Detect Crop
    for crop_name, syns in CROPS.items():
        word_syns = [s for s in syns if not s.isdigit()]
        if any(re.search(rf"(?:^|[\s,।]){re.escape(s)}(?:$|[\s,।])", norm) for s in word_syns):
            extracted["crop"] = crop_name
            break

    # 4. Detect Area (with unit)
    area_norm = (
        norm.replace("बीघे", "bigha")
        .replace("बीघा", "bigha")
        .replace("एकड़", "acre")
        .replace("हेक्टेयर", "ha")
    )
    m_area = re.search(r"(\d+(?:\.\d+)?)\s*(bigha|bighe|acre|acres|ha|hectare)", area_norm)
    if m_area:
        try:
            extracted.update(parse_area(f"{m_area.group(1)} {m_area.group(2)}"))
        except ValueError:
            pass
    else:
        for word, val in sorted(HINDI_NUMBER_WORDS.items(), key=lambda x: -len(x[0])):
            m_sp = re.search(
                rf"(?:^|\s){re.escape(word)}\s*(bigha|bighe|acre|acres|ha|hectare)", area_norm
            )
            if m_sp:
                try:
                    extracted.update(parse_area(f"{val} {m_sp.group(1)}"))
                except ValueError:
                    pass
                break

    # 5. Detect Budget
    budget = parse_spoken_budget(norm)
    if budget is not None and budget >= 100:
        extracted["budget"] = budget

    # 6. Detect 3 NPK numbers if spoken/typed
    try:
        n, p, k = parse_soil(norm)
        extracted["soil_npk"] = [n, p, k]
    except ValueError:
        pass

    return extracted