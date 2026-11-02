from urllib.parse import quote

CROP_HI = {"wheat": "गेहूं", "sugarcane": "गन्ना", "rice": "धान", "maize": "मक्का"}


def format_result_hindi(report: dict, base_url: str) -> str:
    """Format advisory result for WhatsApp – compact single-screen layout."""
    plan = report["plan"]
    inputs = report["inputs"]
    lines = [
        f"🌾 *जल-खाद सलाह*  ⚠️ _KVK से जाँच कराएँ_",
        f"📍 {inputs['village']} • {CROP_HI[inputs['crop']]} • {report['area_ha']:.2f} ha",
    ]
    # ── Shopping: one-line per product ──
    shopping_parts = []
    for row in plan["shopping"]:
        if row["bags"]:
            shopping_parts.append(
                f"  {row.get('product_hi', row['product'])}: "
                f"{row['bags']}×₹{row['cost']:.0f}, {row['apply_kg']:.1f}kg"
            )
    if shopping_parts:
        lines.append("*🛒 खरीदारी*")
        lines.extend(shopping_parts)
    lines.append(
        f"💰 कुल ₹{plan['total_cost']:.0f}/₹{inputs['budget']:.0f} "
        f"| पोषक {plan['minimum_coverage']:.0%}"
    )
    # ── Soil (one line) ──
    if report.get("soil_report"):
        origin = (report.get("soil_origin") or {}).get("label_hi") or "मिट्टी"
        summary = ", ".join(
            f"{item['label_hi'].split(' (')[0]}: {item['rating_hi']}"
            for item in report["soil_report"]["items"][:3]
        )
        lines.append(f"🧪 {origin}: {summary}")
    # ── Schedule (compact) ──
    risk_icon = {"high": "🔴", "unknown": "🟡", "lower": "🟢"}
    sched_parts = []
    for stage in report["schedule"]:
        doses = stage.get("allocations_hi") or stage["allocations"]
        dose = ", ".join(f"{p} {kg:.0f}kg" for p, kg in doses.items())
        icon = risk_icon.get(stage["risk"], "⚪")
        sched_parts.append(f"  {icon} {stage['start'][:10]}: {dose or '—'}")
    if sched_parts:
        lines.append("*📅 कब डालें*")
        lines.extend(sched_parts[:5])  # Cap to 5 entries for compactness
        if len(sched_parts) > 5:
            lines.append(f"  …+{len(sched_parts)-5} और (PDF में देखें)")
    # ── Water (one paragraph) ──
    water = report.get("water")
    if water and water["events"]:
        first = next((e for e in water["events"] if e["das"] >= 0), water["events"][0])
        lines.append(
            f"💧 ~{water['season']['count']} सिंचाई, "
            f"हर बार ~{first['gross_cm']}cm "
            f"({first['litres_per_bigha']:,}L/बीघा)"
        )
        if water.get("realtime"):
            lines.append(f"🌦️ {water['realtime']['advice_hi']}")
    # ── Top tips (max 2) ──
    if report.get("recommendations"):
        for item in report["recommendations"][:2]:
            lines.append(f"✅ {item['title_hi']}")
    # ── Footer ──
    lines.append(f"\n📄 {base_url}/results/{quote(report['id'])}?lang=hi")
    lines.append(
        "1 PDF | 2 अलर्ट | 3 शुरू | 4 विज्ञान\n"
        "STOP=बंद DELETE=मिटाएँ"
    )
    text = "\n".join(lines)
    # WhatsApp rejects bodies over 4,096 characters; truncate safely.
    if len(text) > 3900:
        tail = "\n".join(lines[-2:])
        text = text[: 3890 - len(tail)] + "…\n" + tail
    return text


def format_result_hindi_voice(report: dict) -> str:
    """Return a concise Hindi narration script for TTS audio.

    This strips emoji, markdown formatting, and URLs – producing clean
    Hindi sentences that sound natural when spoken aloud.
    """
    plan = report["plan"]
    inputs = report["inputs"]
    crop_hi = CROP_HI.get(inputs["crop"], inputs["crop"])
    parts = [
        f"आपकी {crop_hi} फसल की सलाह तैयार है।",
        f"गाँव {inputs['village']}, कुल क्षेत्र {report['area_ha']:.2f} हेक्टेयर।",
    ]
    # Shopping
    for row in plan["shopping"]:
        if row["bags"]:
            product = row.get("product_hi", row["product"])
            parts.append(
                f"{product} की {row['bags']} बोरी, लागत {row['cost']:.0f} रुपये।"
            )
    parts.append(
        f"कुल खर्च {plan['total_cost']:.0f} रुपये, बजट {inputs['budget']:.0f} रुपये।"
    )
    # Schedule (first 3)
    for stage in report["schedule"][:3]:
        doses = stage.get("allocations_hi") or stage["allocations"]
        dose_text = ", ".join(f"{p} {kg:.0f} किलो" for p, kg in doses.items())
        if dose_text:
            parts.append(f"तारीख {stage['start'][:10]} को {dose_text} डालें।")
    # Water summary
    water = report.get("water")
    if water and water["events"]:
        first = next((e for e in water["events"] if e["das"] >= 0), water["events"][0])
        parts.append(
            f"लगभग {water['season']['count']} बार सिंचाई करें, "
            f"हर बार {first['litres_per_bigha']} लीटर प्रति बीघा।"
        )
    parts.append("अधिक जानकारी के लिए PDF डाउनलोड करें। धन्यवाद।")
    return " ".join(parts)
