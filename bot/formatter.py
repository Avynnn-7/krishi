from urllib.parse import quote

CROP_HI = {"wheat": "गेहूं", "sugarcane": "गन्ना", "rice": "धान", "maize": "मक्का"}


def format_result_hindi(report: dict, base_url: str) -> str:
    plan = report["plan"]
    inputs = report["inputs"]
    lines = [
        "*जल-खाद | व्यक्तिगत सलाह (परीक्षण)*",
        "⚠️ खेत में उपयोग से पहले कृषि विशेषज्ञ/KVK से जाँच कराएँ।",
        f"📍 {inputs['village']} | 🌾 {CROP_HI[inputs['crop']]} | {report['area_ha']:.3f} ha",
        "\n*🛒 खरीदारी / उपयोग*",
    ]
    for row in plan["shopping"]:
        if row["bags"]:
            lines.append(
                f"• {row.get('product_hi', row['product'])}: {row['bags']} बोरी, ₹{row['cost']:.0f}; "
                f"डालें {row['apply_kg']:.1f} kg, बचेगा {row['leftover_kg']:.1f} kg"
            )
    lines.append(
        f"कुल ₹{plan['total_cost']:.0f} / बजट ₹{inputs['budget']:.0f} | न्यूनतम पोषक पूर्ति {plan['minimum_coverage']:.0%}"
    )
    if report.get("soil_report"):
        origin = (report.get("soil_origin") or {}).get("label_hi") or "मिट्टी कार्ड"
        summary = ", ".join(
            f"{item['label_hi'].split(' (')[0]}: {item['rating_hi']}"
            for item in report["soil_report"]["items"][:3]
        )
        lines.append(f"\n*🧪 {origin}*\n{summary}")
    lines.append("\n*📅 खाद कब डालें*")
    for stage in report["schedule"]:
        doses = stage.get("allocations_hi") or stage["allocations"]
        dose = ", ".join(f"{p} {kg:.1f} kg" for p, kg in doses.items())
        risk = {"high": "भारी वर्षा — रोकें", "unknown": "मौसम फिर देखें", "lower": "कम जोखिम"}[
            stage["risk"]
        ]
        lines.append(f"• {stage['start'][:10]}: {dose or '—'} ({risk})")
    water = report.get("water")
    if water and water["events"]:
        first = next((e for e in water["events"] if e["das"] >= 0), water["events"][0])
        season = water["season"]
        lines.append(f"\n*💧 सिंचाई ({water['method_hi']})*")
        lines.append(
            f"लगभग {season['count']} सिंचाई; हर बार ~{first['gross_cm']} cm "
            f"(≈ {first['litres_per_bigha']:,} लीटर प्रति बीघा, पूरे खेत में {first['volume_m3']:.0f} m³)"
        )
        lines.append(f"पहली: {first['date']} ({first['stage_hi']})")
        if first.get("pump_hours"):
            lines.append(f"पंप समय: ~{first['pump_hours']:.1f} घंटे प्रति सिंचाई")
        if water.get("realtime"):
            lines.append(f"🌦️ *आज का मौसम व सिंचाई*: {water['realtime']['advice_hi']}")
    if report.get("recommendations"):
        lines.append("\n*✅ आपके लिए मुख्य सुझाव*")
        for item in report["recommendations"][:3]:
            lines.append(f"• {item['title_hi']}")
    lines.append(f"\nपूरी रिपोर्ट: {base_url}/results/{quote(report['id'])}?lang=hi")
    lines.append(
        "\n1 PDF | 2 मौसम अलर्ट (सहमति: फोन/निर्देशांक सहेजें) | 3 फिर शुरू | 4 वैज्ञानिक आधार\nSTOP = अलर्ट बंद; DELETE = बॉट डेटा मिटाएँ"
    )
    text = "\n".join(lines)
    # WhatsApp rejects bodies over 4,096 characters; keep the report link and menu intact.
    if len(text) > 3900:
        tail = "\n".join(lines[-2:])
        text = text[: 3890 - len(tail)] + "…\n" + tail
    return text
