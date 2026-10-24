"""Soil Health Card interpretation: ratings, plain-language meaning and field actions."""

import json
from functools import lru_cache
from pathlib import Path

from engine.models import P_TO_P2O5, Soil

LABELS = {
    "N": ("Available nitrogen (N)", "उपलब्ध नाइट्रोजन (N)"),
    "P": ("Available phosphorus (P)", "उपलब्ध फॉस्फोरस (P)"),
    "K": ("Available potassium (K)", "उपलब्ध पोटाश (K)"),
    "organic_carbon": ("Organic carbon (OC)", "जैविक कार्बन (OC)"),
    "ph": ("Soil reaction (pH)", "मिट्टी का pH"),
    "ec": ("Salinity (EC)", "लवणता (EC)"),
    "sulphur": ("Sulphur (S)", "गंधक (S)"),
    "zinc": ("Zinc (Zn)", "जिंक (Zn)"),
    "iron": ("Iron (Fe)", "लोहा (Fe)"),
    "manganese": ("Manganese (Mn)", "मैंगनीज़ (Mn)"),
    "copper": ("Copper (Cu)", "तांबा (Cu)"),
    "boron": ("Boron (B)", "बोरॉन (B)"),
}
RATING_HI = {
    "low": "कम",
    "medium": "मध्यम",
    "high": "अधिक",
    "deficient": "कमी",
    "sufficient": "पर्याप्त",
    "acidic": "अम्लीय",
    "neutral": "सामान्य",
    "alkaline": "क्षारीय",
    "sodic": "अधिक क्षारीय",
    "normal": "सामान्य",
    "saline": "लवणीय",
    "very_saline": "अधिक लवणीय",
}
MEANING = {
    ("N", "low"): (
        "Crop will respond strongly to nitrogen. Split urea and apply just before irrigation.",
        "फसल नाइट्रोजन पर अच्छा असर देगी। यूरिया किस्तों में, सिंचाई से ठीक पहले डालें।",
    ),
    ("N", "medium"): ("Normal nitrogen dose is suitable.", "सामान्य नाइट्रोजन मात्रा उचित है।"),
    ("N", "high"): (
        "Reduce nitrogen; excess causes lodging and pests.",
        "नाइट्रोजन घटाएँ; ज़्यादा से फसल गिरती है और कीट बढ़ते हैं।",
    ),
    ("P", "low"): (
        "Phosphorus needed at sowing (DAP/SSP/NPK in furrows).",
        "बुवाई के समय फॉस्फोरस ज़रूरी (DAP/SSP/NPK कूंड़ में)।",
    ),
    ("P", "medium"): ("Normal phosphorus dose.", "सामान्य फॉस्फोरस मात्रा।"),
    ("P", "high"): (
        "Soil already rich in P. Cut DAP — extra DAP is wasted money.",
        "मिट्टी में फॉस्फोरस पहले से ज़्यादा है। DAP घटाएँ — अतिरिक्त DAP पैसे की बर्बादी है।",
    ),
    ("K", "low"): (
        "Potash needed; improves grain filling and lodging resistance.",
        "पोटाश ज़रूरी; दाना भराव और तने की मज़बूती बढ़ती है।",
    ),
    ("K", "medium"): ("Normal potash dose.", "सामान्य पोटाश मात्रा।"),
    ("K", "high"): ("Potash can be reduced.", "पोटाश कम कर सकते हैं।"),
    ("organic_carbon", "low"): (
        "Soil is low in organic matter: holds less water and nutrients. Add FYM/compost, green manure, keep residue — do not burn.",
        "मिट्टी में जैविक पदार्थ कम: पानी व पोषक कम रोकती है। गोबर खाद/कम्पोस्ट, हरी खाद डालें, पराली न जलाएँ।",
    ),
    ("organic_carbon", "medium"): (
        "Maintain with FYM and residue incorporation.",
        "गोबर खाद और फसल अवशेष मिलाकर बनाए रखें।",
    ),
    ("organic_carbon", "high"): (
        "Good organic matter. Maintain it.",
        "जैविक पदार्थ अच्छा है। बनाए रखें।",
    ),
    ("ph", "acidic"): (
        "Acidic: P and molybdenum less available. Liming may help — ask the lab for lime requirement.",
        "अम्लीय मिट्टी: फॉस्फोरस कम उपलब्ध। चूना लाभदायक हो सकता है — लैब से चूने की मात्रा पूछें।",
    ),
    ("ph", "neutral"): ("Ideal range for most crops.", "अधिकांश फसलों के लिए आदर्श।"),
    ("ph", "alkaline"): (
        "Mildly alkaline: zinc/iron deficiency more likely. Prefer SSP/ammonium fertilizers; add organic matter.",
        "हल्की क्षारीय: जिंक/लोहे की कमी की संभावना। SSP उपयोगी; जैविक खाद डालें।",
    ),
    ("ph", "sodic"): (
        "Strongly alkaline (possible sodic soil). Gypsum based on lab gypsum requirement; good drainage needed.",
        "अधिक क्षारीय (ऊसर की संभावना)। लैब से जिप्सम की मात्रा जाँचकर जिप्सम डालें; पानी निकासी ज़रूरी।",
    ),
    ("ec", "normal"): ("No salinity problem.", "लवणता की समस्या नहीं।"),
    ("ec", "saline"): (
        "Salinity can hurt germination. Irrigate lightly and often; avoid salty tubewell water if possible.",
        "लवणता से अंकुरण पर असर। हल्की और बार-बार सिंचाई; खारे पानी से बचें।",
    ),
    ("ec", "very_saline"): (
        "Harmful salinity. Needs leaching with good water and drainage — consult KVK.",
        "हानिकारक लवणता। अच्छे पानी से लवण धोना व निकासी ज़रूरी — KVK से सलाह लें।",
    ),
}
MICRO_ACTION = {
    "zinc": (
        "Apply zinc sulphate heptahydrate (21% Zn) 25 kg/ha at sowing; or spray 0.5% zinc sulphate if symptoms appear.",
        "बुवाई पर जिंक सल्फेट (21%) 25 kg/ha डालें; लक्षण दिखें तो 0.5% जिंक सल्फेट का छिड़काव।",
        25,
        "Zinc sulphate (21% Zn)",
        "जिंक सल्फेट (21%)",
    ),
    "sulphur": (
        "Supply 20–40 kg S/ha: choose SSP as phosphorus source or apply ~200 kg/ha gypsum at sowing.",
        "20–40 kg S/ha दें: फॉस्फोरस के लिए SSP चुनें या बुवाई पर ~200 kg/ha जिप्सम।",
        200,
        "Gypsum (agricultural)",
        "जिप्सम",
    ),
    "boron": (
        "Apply borax 10 kg/ha at sowing (do not exceed — boron is toxic in excess).",
        "बुवाई पर बोरेक्स 10 kg/ha (अधिक न डालें — ज़्यादा बोरॉन हानिकारक)।",
        10,
        "Borax",
        "बोरेक्स",
    ),
    "iron": (
        "Soil application is inefficient: spray 0.5–1% ferrous sulphate (2–3 sprays) when yellowing appears.",
        "मिट्टी में डालना कम असरदार: पीलापन दिखे तो 0.5–1% फेरस सल्फेट के 2–3 छिड़काव।",
        0,
        "",
        "",
    ),
    "manganese": (
        "Spray 0.5% manganese sulphate (2–3 sprays), especially wheat on light soils.",
        "0.5% मैंगनीज़ सल्फेट के 2–3 छिड़काव, खासकर हल्की मिट्टी में गेहूं।",
        0,
        "",
        "",
    ),
    "copper": (
        "Rare. Confirm with the lab before applying copper sulphate.",
        "दुर्लभ। कॉपर सल्फेट से पहले लैब से पुष्टि करें।",
        0,
        "",
        "",
    ),
}


@lru_cache(maxsize=4)
def load_ratings(data_dir: Path) -> dict:
    return json.loads((data_dir / "soil_ratings.json").read_text())


def three_level(value: float, low: float, high: float) -> str:
    if value < low:
        return "low"
    if value > high:
        return "high"
    return "medium"


def gauge(value: float, low: float, high: float) -> float:
    """Position on a 0–1 scale where 1/3 and 2/3 mark the low/high limits."""
    if value <= low:
        return max(0.0, value / low / 3) if low else 0.0
    if value <= high:
        return 1 / 3 + (value - low) / (high - low) / 3
    return min(1.0, 2 / 3 + (value - high) / high / 3)


def ph_class(ph: float) -> str:
    if ph < 6.5:
        return "acidic"
    if ph <= 7.5:
        return "neutral"
    if ph <= 8.5:
        return "alkaline"
    return "sodic"


def ec_class(ec: float) -> str:
    if ec < 1:
        return "normal"
    if ec <= 4:
        return "saline"
    return "very_saline"


def interpret_soil(soil: Soil, data_dir: Path, area_ha: float = 1.0) -> dict:
    ratings = load_ratings(data_dir)
    macro, micro = ratings["macro"], ratings["micro"]
    elemental = soil.elemental_values()
    items, amendments, plausibility = [], [], []
    nutrient_ratings = {}
    for key, value in (("N", elemental["N"]), ("P", elemental["P"]), ("K", elemental["K"])):
        limits = macro[key]
        rating = three_level(value, limits["low"], limits["high"])
        nutrient_ratings[{"N": "N", "P": "P2O5", "K": "K2O"}[key]] = rating
        shown = value
        unit = f"{limits['unit']} ({limits['basis']})"
        if key == "P" and soil.basis == "oxide":
            unit += f" — entered as P₂O₅ {soil.P:g}"
        if key == "K" and soil.basis == "oxide":
            unit += f" — entered as K₂O {soil.K:g}"
        items.append(entry(key, shown, unit, rating, gauge(value, limits["low"], limits["high"])))
    if elemental["N"] > 1200:
        plausibility.append("N above 1,200 kg/ha is unusual — check the unit (ppm × 2.24 = kg/ha).")
    if elemental["P"] > 150:
        plausibility.append(
            f"P above 150 kg/ha is unusual. If your card shows P₂O₅, choose the oxide basis (P = P₂O₅ ÷ {P_TO_P2O5})."
        )
    if elemental["K"] > 1500:
        plausibility.append("K above 1,500 kg/ha is unusual — check the unit and basis.")
    if soil.organic_carbon is not None:
        limits = macro["organic_carbon"]
        rating = three_level(soil.organic_carbon, limits["low"], limits["high"])
        items.append(
            entry(
                "organic_carbon",
                soil.organic_carbon,
                "%",
                rating,
                gauge(soil.organic_carbon, limits["low"], limits["high"]),
            )
        )
        if soil.organic_carbon > 5:
            plausibility.append(
                "Organic carbon above 5% is unusual for cropland — check the value."
            )
    if soil.ph is not None:
        rating = ph_class(soil.ph)
        items.append(entry("ph", soil.ph, "", rating, min(1, soil.ph / 14)))
    if soil.ec is not None:
        rating = ec_class(soil.ec)
        items.append(entry("ec", soil.ec, "dS/m", rating, min(1, soil.ec / 8)))
    for key, limits in micro.items():
        value = getattr(soil, key)
        if value is None:
            continue
        rating = "deficient" if value < limits["critical"] else "sufficient"
        item = entry(key, value, limits["unit"], rating, min(1, value / (limits["critical"] * 3)))
        if rating == "deficient":
            action_en, action_hi, kg_ha, product_en, product_hi = MICRO_ACTION[key]
            item["meaning_en"], item["meaning_hi"] = action_en, action_hi
            if kg_ha:
                amendments.append(
                    {
                        "nutrient": key,
                        "product_en": product_en,
                        "product_hi": product_hi,
                        "kg_ha": kg_ha,
                        "kg_field": round(kg_ha * area_ha, 1),
                        "how_en": action_en,
                        "how_hi": action_hi,
                    }
                )
        else:
            item["meaning_en"] = f"Above critical limit {limits['critical']} {limits['unit']}."
            item["meaning_hi"] = f"सीमा {limits['critical']} {limits['unit']} से ऊपर — पर्याप्त।"
        items.append(item)
    if soil.ph is not None and soil.ph > 8.5:
        amendments.append(
            {
                "nutrient": "ph",
                "product_en": "Gypsum (per lab gypsum requirement)",
                "product_hi": "जिप्सम (लैब की बताई मात्रा)",
                "kg_ha": None,
                "kg_field": None,
                "how_en": "Quantity depends on the gypsum-requirement test; apply before the season with good drainage.",
                "how_hi": "मात्रा जिप्सम-आवश्यकता जाँच पर निर्भर; मौसम से पहले, पानी निकासी के साथ।",
            }
        )
    flags = sum(
        1
        for i in items
        if i["rating"] in {"low", "deficient", "sodic", "very_saline", "acidic", "saline"}
    )
    return {
        "items": items,
        "nutrient_ratings": nutrient_ratings,
        "amendments": amendments,
        "plausibility": plausibility,
        "attention_count": flags,
        "source": ratings["source"],
    }


def entry(key: str, value: float, unit: str, rating: str, position: float) -> dict:
    en, hi = LABELS[key]
    meaning = MEANING.get((key, rating), ("", ""))
    return {
        "key": key,
        "label_en": en,
        "label_hi": hi,
        "value": round(value, 3),
        "unit": unit,
        "rating": rating,
        "rating_hi": RATING_HI[rating],
        "gauge": round(position, 3),
        "meaning_en": meaning[0],
        "meaning_hi": meaning[1],
        "tone": "bad"
        if rating in {"low", "deficient", "sodic", "very_saline"}
        else "warn"
        if rating in {"acidic", "alkaline", "saline", "high"} and key not in {"organic_carbon"}
        else "good",
    }
