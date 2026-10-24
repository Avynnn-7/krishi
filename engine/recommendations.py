"""Personal, prioritised action list built from all advisory components."""

from engine.models import AdvisoryInput

NUTRIENT_HI = {"N": "नाइट्रोजन", "P2O5": "फॉस्फोरस (P₂O₅)", "K2O": "पोटाश (K₂O)"}
SOIL_LAB_EN = "District Soil Testing Laboratory, Bahadrabad (01334-239034, as listed in the project specification) or KVK Dhanauri"
SOIL_LAB_HI = (
    "जिला मृदा परीक्षण प्रयोगशाला, बहादराबाद (01334-239034, परियोजना विवरण अनुसार) या KVK धनौरी"
)


def rec(priority: int, category: str, en: str, hi: str, detail_en: str, detail_hi: str) -> dict:
    return {
        "priority": priority,
        "category": category,
        "title_en": en,
        "title_hi": hi,
        "detail_en": detail_en,
        "detail_hi": detail_hi,
    }


def build_recommendations(
    inputs: AdvisoryInput,
    breakdown: dict,
    soil_report: dict | None,
    plan: dict,
    practice: dict | None,
    water: dict,
    products: dict,
) -> list[dict]:
    items = []
    area = inputs.area_ha
    if inputs.soil is None:
        items.append(
            rec(
                1,
                "soil",
                "Get your soil tested before the next season",
                "अगले मौसम से पहले मिट्टी की जाँच कराएँ",
                f"Without a test this plan uses a general dose. District surveys indicate low N and high P, but your field may differ. "
                f"Contact the {SOIL_LAB_EN}. Soil Health Card testing is free.",
                f"जाँच के बिना सामान्य मात्रा ली गई है। ज़िले में आमतौर पर N कम और P ज़्यादा पाया गया है, पर आपका खेत अलग हो सकता है। "
                f"{SOIL_LAB_HI} से संपर्क करें। मृदा स्वास्थ्य कार्ड जाँच निःशुल्क है।",
            )
        )
    ratings = breakdown.get("ratings") or {}
    if ratings.get("P2O5") == "high":
        items.append(
            rec(
                1,
                "money",
                "Phosphorus is high: use less DAP",
                "फॉस्फोरस ज़्यादा है: DAP कम डालें",
                f"Phosphorus need was reduced to {breakdown['per_ha']['P2O5']:.0f} kg P₂O₅/ha (75% of the general dose). "
                "Extra DAP adds cost without extra yield; spend on nitrogen timing and potash instead.",
                f"फॉस्फोरस की ज़रूरत {breakdown['per_ha']['P2O5']:.0f} kg P₂O₅/ha (सामान्य का 75%) रखी गई। "
                "अतिरिक्त DAP से खर्च बढ़ता है, उपज नहीं; पैसा नाइट्रोजन के सही समय और पोटाश पर लगाएँ।",
            )
        )
    if ratings.get("N") == "low":
        items.append(
            rec(
                1,
                "timing",
                "Nitrogen is low: split urea and time it with water",
                "नाइट्रोजन कम है: यूरिया किस्तों में, पानी के समय के साथ",
                "N dose raised to 125% of the general recommendation. Never put all urea at once; apply each split on moist soil just before irrigation so water carries it to the roots.",
                "N मात्रा सामान्य की 125% रखी गई। सारा यूरिया एक बार में न डालें; हर किस्त नम मिट्टी पर सिंचाई से ठीक पहले डालें ताकि पानी उसे जड़ों तक ले जाए।",
            )
        )
    if practice:
        for nutrient, diff in practice["difference"].items():
            need = plan["required"][nutrient]
            if diff > max(5, 0.2 * need):
                items.append(
                    rec(
                        1 if nutrient == "P2O5" else 2,
                        "money",
                        f"Your usual practice over-applies {nutrient} by {diff:.0f} kg",
                        f"आपकी सामान्य आदत में {NUTRIENT_HI[nutrient]} {diff:.0f} kg ज़्यादा जाता है",
                        f"Usual practice supplies {practice['nutrients'][nutrient]:.0f} kg vs {need:.0f} kg needed for this field.",
                        f"सामान्य आदत से {practice['nutrients'][nutrient]:.0f} kg जाता है, जबकि इस खेत को {need:.0f} kg चाहिए।",
                    )
                )
            elif -diff > max(5, 0.2 * need):
                items.append(
                    rec(
                        2,
                        "fertilizer",
                        f"Your usual practice under-supplies {nutrient} by {-diff:.0f} kg",
                        f"आपकी सामान्य आदत में {NUTRIENT_HI[nutrient]} {-diff:.0f} kg कम जाता है",
                        "This nutrient may be limiting yield. The plan below rebalances it within your budget.",
                        "यह पोषक उपज को सीमित कर सकता है। नीचे की योजना बजट के भीतर संतुलन करती है।",
                    )
                )
        saving = practice["cost"] - plan["total_cost"]
        if saving > max(100, 0.05 * practice["cost"]):
            items.append(
                rec(
                    2,
                    "money",
                    f"Purchase cost is ₹{saving:,.0f} lower than your usual spend",
                    f"सामान्य खर्च से खरीद ₹{saving:,.0f} कम",
                    "Compare nutrient coverage too: a cheaper plan is only better if it still meets the crop's needs.",
                    "पोषक पूर्ति भी देखें: सस्ती योजना तभी बेहतर है जब फसल की ज़रूरत पूरी हो।",
                )
            )
    if plan["minimum_coverage"] < 0.95:
        weakest = min(plan["coverage"], key=plan["coverage"].get)
        items.append(
            rec(
                1,
                "money",
                f"Budget is short: {weakest} is only {plan['coverage'][weakest]:.0%} covered",
                f"बजट कम है: {NUTRIENT_HI[weakest]} केवल {plan['coverage'][weakest]:.0%} पूरा",
                "Increase the budget if possible, or prioritise this nutrient. Partial doses still help; do not skip nitrogen splits.",
                "संभव हो तो बजट बढ़ाएँ या इस पोषक को प्राथमिकता दें। आंशिक मात्रा भी लाभ देती है; नाइट्रोजन की किस्तें न छोड़ें।",
            )
        )
    if soil_report:
        for amendment in soil_report["amendments"]:
            quantity_en = (
                f"{amendment['kg_field']:g} kg for this field ({amendment['kg_ha']:g} kg/ha). "
                if amendment["kg_field"]
                else ""
            )
            quantity_hi = (
                f"इस खेत के लिए {amendment['kg_field']:g} kg ({amendment['kg_ha']:g} kg/ha)। "
                if amendment["kg_field"]
                else ""
            )
            items.append(
                rec(
                    2,
                    "soil",
                    f"Correct {amendment['nutrient']}: {amendment['product_en']}",
                    f"सुधार: {amendment['product_hi']}",
                    quantity_en + amendment["how_en"],
                    quantity_hi + amendment["how_hi"],
                )
            )
        oc = next((i for i in soil_report["items"] if i["key"] == "organic_carbon"), None)
        if oc and oc["rating"] == "low" and inputs.fym_t_ha < 5:
            items.append(
                rec(
                    2,
                    "soil",
                    "Build organic matter: 10 t/ha FYM or a green-manure crop",
                    "जैविक पदार्थ बढ़ाएँ: 10 टन/हे. गोबर खाद या हरी खाद",
                    f"About {10 * area:.1f} t well-rotted FYM for this field, dhaincha/moong green manure, and no residue burning. Better water holding means fewer irrigations.",
                    f"इस खेत के लिए लगभग {10 * area:.1f} टन सड़ी गोबर खाद, ढैंचा/मूंग हरी खाद, पराली न जलाएँ। ज़्यादा नमी रुकेगी, कम सिंचाई लगेगी।",
                )
            )
        for warning in soil_report["plausibility"]:
            items.append(
                rec(
                    1,
                    "soil",
                    "Check your soil card values",
                    "मिट्टी कार्ड के मान जाँचें",
                    warning,
                    warning,
                )
            )
    selected = next(c for c in water["comparison"] if c["selected"])
    better = [c for c in water["comparison"] if c["season_m3"] < selected["season_m3"] * 0.9]
    if better and selected["season_m3"]:
        # Prefer the cheapest practical step first; costlier options stay visible in the comparison.
        preference = [
            "border",
            "rice_awd",
            "furrow",
            "laser_border",
            "raised_bed",
            "sprinkler",
            "drip",
        ]
        best = min(better, key=lambda c: preference.index(c["id"]) if c["id"] in preference else 99)
        saved = selected["season_m3"] - best["season_m3"]
        hours = (
            f" (~{saved * 1000 / inputs.flow_lps / 3600:.0f} pump hours)" if inputs.flow_lps else ""
        )
        hours_hi = (
            f" (~{saved * 1000 / inputs.flow_lps / 3600:.0f} पंप घंटे)" if inputs.flow_lps else ""
        )
        items.append(
            rec(
                1 if selected["id"] in {"wild_flood", "rice_cf"} else 3,
                "water",
                f"Switch to {best['name_en']}: save ~{saved:,.0f} m³ water this season{hours}",
                f"{best['name_hi']} अपनाएँ: इस मौसम ~{saved * 1000:,.0f} लीटर पानी बचेगा{hours_hi}",
                "Less water standing on the field also means less urea washed below the roots. See the method comparison for pros and cons.",
                "खेत में कम पानी खड़ा रहने से यूरिया भी जड़ों से नीचे कम बहता है। फायदे-नुकसान तुलना तालिका में देखें।",
            )
        )
    if water["turn"] and water["turn"]["coverage"] < 1:
        turn = water["turn"]
        items.append(
            rec(
                1,
                "water",
                f"Your water turn covers only {turn['coverage']:.0%} of one irrigation",
                f"आपकी पानी की बारी एक सिंचाई का केवल {turn['coverage']:.0%} पूरा करती है",
                f"A full irrigation needs ~{turn['hours_needed']:.1f} h at your flow. Irrigate the highest-priority part first, use smaller checks, or arrange extra tubewell hours.",
                f"आपके बहाव पर पूरी सिंचाई में ~{turn['hours_needed']:.1f} घंटे लगेंगे। पहले ज़रूरी हिस्सा सींचें, छोटी क्यारियाँ बनाएँ, या ट्यूबवेल से अतिरिक्त घंटे लें।",
            )
        )
    if inputs.texture == "sandy":
        items.append(
            rec(
                2,
                "water",
                "Sandy soil: light, frequent irrigations",
                "रेतीली मिट्टी: हल्की और बार-बार सिंचाई",
                "Sandy soil holds little water; heavy flooding pushes water and urea below the roots. Use short checks or sprinklers.",
                "रेतीली मिट्टी कम पानी रोकती है; भारी पानी से पानी और यूरिया जड़ों से नीचे चले जाते हैं। छोटी क्यारियाँ या फव्वारा अपनाएँ।",
            )
        )
    if inputs.crop == "sugarcane":
        items.append(
            rec(
                3,
                "soil",
                "Intercrop moong/urad between cane rows",
                "गन्ने की कतारों के बीच मूंग/उड़द",
                "Extra income in the first months and better soil health. Use the intercrop calculator with your own prices.",
                "शुरुआती महीनों में अतिरिक्त आय और बेहतर मिट्टी। अपने भाव के साथ अंतरफसल गणना देखें।",
            )
        )
        items.append(
            rec(
                3,
                "water",
                "Trash mulching saves irrigation in summer",
                "पत्ती (ट्रैश) मल्च से गर्मी में सिंचाई बचती है",
                "Spread dry cane leaves between rows after the first earthing-up to reduce evaporation and weeds.",
                "पहली मिट्टी चढ़ाने के बाद कतारों के बीच सूखी पत्तियाँ बिछाएँ — वाष्पन और खरपतवार कम।",
            )
        )
    items.append(
        rec(
            3,
            "money",
            "Buy at MRP and take a bill",
            "MRP पर खरीदें और बिल लें",
            "Prices here are reference values; compare with your dealer bill and report overcharging to the agriculture department.",
            "यहाँ भाव संदर्भ हेतु हैं; दुकान के बिल से मिलाएँ और ज़्यादा दाम लेने की शिकायत कृषि विभाग में करें।",
        )
    )
    unique, seen = [], set()
    for item in sorted(items, key=lambda i: i["priority"]):
        if item["title_en"] not in seen:
            seen.add(item["title_en"])
            unique.append(item)
    return unique
