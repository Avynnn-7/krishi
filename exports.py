from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle


def advisory_pdf(report: dict, font_path: Path, hindi: bool = False) -> bytes:
    if "JalKhaddSans" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("JalKhaddSans", str(font_path), shapable=True))
    style = ParagraphStyle(
        "body", fontName="JalKhaddSans", fontSize=7.6, leading=10.5, shaping=True
    )
    heading = ParagraphStyle(
        "heading", parent=style, fontSize=15, leading=20, textColor=colors.HexColor("#164c35")
    )
    section = ParagraphStyle(
        "section",
        parent=style,
        fontSize=10,
        leading=14,
        spaceBefore=6,
        spaceAfter=3,
        textColor=colors.HexColor("#164c35"),
    )
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=28, leftMargin=28, topMargin=22, bottomMargin=22
    )
    lang = "hi" if hindi else "en"

    def tr(en: str, hi: str) -> str:
        return hi if hindi else en

    def paragraph(text: str, kind: ParagraphStyle = style) -> Paragraph:
        return Paragraph(escape(str(text)), kind)

    def table(header: list[str], rows: list[list], widths: list[int]) -> Table:
        data = [[paragraph(h) for h in header]] + [[paragraph(v) for v in row] for row in rows]
        result = Table(data, colWidths=widths, repeatRows=1)
        result.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e3eee6")),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#d4ded5")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        return result

    inputs, plan, water = report["inputs"], report["plan"], report.get("water")
    content = [
        paragraph(
            tr(
                "JAL-KHADD | Personal field advisory (prototype)",
                "जल-खाद | व्यक्तिगत खेत सलाह (परीक्षण)",
            ),
            heading,
        ),
        paragraph(
            tr(
                "EXPERT REVIEW REQUIRED before buying or applying. Not a guaranteed prescription.",
                "खरीद या उपयोग से पहले कृषि विशेषज्ञ/KVK से जाँच ज़रूरी। उपज की गारंटी नहीं।",
            )
        ),
        paragraph(
            f"{inputs['village']} / {inputs['block']} | {inputs['crop']} | {report['area_ha']:.3f} ha | "
            f"{tr('Sown', 'बुवाई')} {inputs['sowing_date']} | {tr('Budget', 'बजट')} INR {inputs['budget']:.0f}"
        ),
        paragraph(report["method"]),
    ]
    if report.get("recommendations"):
        content.append(paragraph(tr("Your top actions", "आपके मुख्य सुझाव"), section))
        for index, item in enumerate(report["recommendations"][:6], 1):
            content.append(
                paragraph(f"{index}. {item['title_' + lang]} — {item['detail_' + lang]}")
            )
    content.append(paragraph(tr("Shopping list", "खरीदारी सूची"), section))
    rows = [
        [
            row.get("product_hi", row["product"]) if hindi else row["product"],
            row["bags"],
            f"{row['cost']:.0f}",
            f"{row['apply_kg']:.1f}",
            f"{row['leftover_kg']:.1f}",
        ]
        for row in plan["shopping"]
        if row["bags"]
    ] or [["—", 0, "0", "0", "0"]]
    rows.append([tr("Total", "कुल"), "", f"{plan['total_cost']:.0f}", "", ""])
    content.append(
        table(
            [
                tr("Product", "खाद"),
                tr("Bags", "बोरी"),
                "INR",
                tr("Apply kg", "डालें kg"),
                tr("Left kg", "बचेगा kg"),
            ],
            rows,
            [170, 55, 90, 110, 110],
        )
    )
    content.append(
        paragraph(
            tr("Nutrient coverage (not yield): ", "पोषक पूर्ति (उपज नहीं): ")
            + " | ".join(f"{n} {plan['coverage'][n]:.0%}" for n in plan["coverage"])
        )
    )
    content.append(paragraph(tr("When to apply fertilizer", "खाद कब डालें"), section))
    risk_names = {
        "high": tr("HOLD: heavy rain", "रोकें: भारी बारिश"),
        "unknown": tr("check weather", "मौसम देखें"),
        "lower": tr("lower risk", "कम जोखिम"),
    }
    content.append(
        table(
            [
                tr("Date (IST)", "तारीख"),
                tr("Stage", "अवस्था"),
                tr("Dose", "मात्रा"),
                tr("Rain risk", "वर्षा"),
            ],
            [
                [
                    f"{s['start'][:10]} {s['start'][11:16]}",
                    s.get("stage_hi", s["stage"]) if hindi else s["stage"],
                    ", ".join(
                        f"{p} {kg:.1f} kg"
                        for p, kg in (
                            s.get("allocations_hi")
                            if hindi and s.get("allocations_hi")
                            else s["allocations"]
                        ).items()
                    )
                    or "—",
                    risk_names[s["risk"]],
                ]
                for s in report["schedule"]
            ],
            [90, 120, 220, 105],
        )
    )
    if report.get("soil_report"):
        content.append(
            paragraph(tr("Soil Health Card explained", "मृदा स्वास्थ्य कार्ड का मतलब"), section)
        )
        content.append(
            table(
                [
                    tr("Parameter", "मान"),
                    tr("Value", "अंक"),
                    tr("Rating", "स्तर"),
                    tr("Meaning / action", "मतलब / क्या करें"),
                ],
                [
                    [
                        i["label_" + lang],
                        f"{i['value']} {i['unit'].split(' (')[0]}",
                        i["rating_hi"] if hindi else i["rating"],
                        i["meaning_" + lang],
                    ]
                    for i in report["soil_report"]["items"]
                ],
                [105, 70, 55, 305],
            )
        )
    if water:
        content.append(
            paragraph(
                tr("Irrigation plan", "सिंचाई योजना") + f" — {water['method_' + lang]}", section
            )
        )
        season = water["season"]
        content.append(
            paragraph(
                tr(
                    f"{season['count']} irrigations, total ~{season['gross_cm']} cm = {season['volume_m3']:.0f} m³ for this field.",
                    f"{season['count']} सिंचाई, कुल ~{season['gross_cm']} cm = इस खेत में {season['volume_m3']:.0f} m³।",
                )
            )
        )
        if water["events"]:
            content.append(
                table(
                    [
                        "#",
                        tr("Date", "तारीख"),
                        tr("Stage", "अवस्था"),
                        tr("Depth", "गहराई"),
                        tr("L/bigha", "लीटर/बीघा"),
                        tr("Field m³", "खेत m³"),
                        tr("Pump h", "पंप घंटे"),
                    ],
                    [
                        [
                            e["number"],
                            e["date"],
                            e["stage_" + lang]
                            + (tr(" (if dry)", " (सूखा हो तो)") if e.get("conditional") else ""),
                            f"{e['gross_cm']} cm",
                            f"{e['litres_per_bigha']:,}",
                            f"{e['volume_m3']:.0f}",
                            e["pump_hours"] if e["pump_hours"] else "—",
                        ]
                        for e in water["events"][:16]
                    ],
                    [22, 62, 150, 52, 72, 72, 60],
                )
            )
        for rule in water["how_" + lang][:4]:
            content.append(paragraph("• " + rule))
    content.append(paragraph(tr("Cautions", "सावधानियाँ"), section))
    content.append(
        paragraph(
            tr(
                "Dates are provisional; do not combine missed doses. Recheck weather 48 h before urea or irrigation; "
                "hold during heavy rain. Apply the kg shown, not whole bags. Prices are reference values — buy at MRP with a bill. "
                "Bigha = Uttarakhand ~632 m² unless stated.",
                "तारीखें अनुमानित हैं; छूटी मात्रा एक साथ न डालें। यूरिया या सिंचाई से 48 घंटे पहले मौसम देखें; भारी बारिश में रोकें। "
                "पूरी बोरी नहीं, बताए kg डालें। भाव संदर्भ हेतु — MRP पर बिल के साथ खरीदें। बीघा = उत्तराखंड ~632 m² (जब तक अलग न लिखा हो)।",
            )
        )
    )
    content.append(
        paragraph(
            tr(
                "Soil testing and review: KVK Dhanauri or the district soil testing laboratory.",
                "मिट्टी जाँच और सलाह: KVK धनौरी या जिला मृदा परीक्षण प्रयोगशाला।",
            )
        )
    )
    content.append(paragraph(f"Report: {report['id']} | {report['created_at'][:10]}"))
    doc.build(content)
    return buffer.getvalue()


def calendar_export(report: dict) -> str:
    def escaped(value: str) -> str:
        return (
            value.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")
        )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Jal-Khadd//Prototype//EN",
        "CALSCALE:GREGORIAN",
    ]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for i, stage in enumerate(report["schedule"]):
        start = datetime.fromisoformat(stage["start"]).astimezone(timezone.utc)
        end = datetime.fromisoformat(stage["end"]).astimezone(timezone.utc)
        if end == start:
            from datetime import timedelta

            end = start + timedelta(hours=1)
        notes = (
            " ".join(stage["notes"])
            + " Doses: "
            + ", ".join(f"{p}: {kg:.2f} kg" for p, kg in stage["allocations"].items())
        )
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{report['id']}-{i}@jal-khadd.local",
                f"DTSTAMP:{stamp}",
                f"DTSTART:{start:%Y%m%dT%H%M%SZ}",
                f"DTEND:{end:%Y%m%dT%H%M%SZ}",
                "SUMMARY:" + escaped(f"REVIEW REQUIRED [{stage['risk']}] {stage['stage']}"),
                "DESCRIPTION:" + escaped(notes),
                "STATUS:TENTATIVE",
                "END:VEVENT",
            ]
        )
    water = report.get("water") or {}
    for i, event in enumerate(water.get("events", [])):
        day = datetime.fromisoformat(event["date"])
        summary = (
            f"Irrigation {event['number']}: ~{event['gross_cm']} cm ({event['volume_m3']:.0f} m3)"
        )
        if event.get("conditional"):
            summary += " - only if soil is dry"
        details = (
            f"{event['stage_en']}. About {event['litres_per_bigha']:,} litres per Uttarakhand bigha. "
            "Check soil moisture and the forecast first."
        )
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{report['id']}-water-{i}@jal-khadd.local",
                f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
                "SUMMARY:" + escaped(summary),
                "DESCRIPTION:" + escaped(details),
                "STATUS:TENTATIVE",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    # RFC 5545 folds at 75 octets, without splitting a UTF-8 code point.
    folded = []
    for line in lines:
        chunk = ""
        for char in line:
            if len((chunk + char).encode()) > 75:
                folded.append(chunk)
                chunk = " "
            chunk += char
        folded.append(chunk)
    return "\r\n".join(folded) + "\r\n"
