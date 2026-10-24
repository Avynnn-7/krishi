import math
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from engine.models import AdvisoryInput

IST = ZoneInfo("Asia/Kolkata")
STAGES = {
    "wheat": [("Basal / sowing", 0), ("Crown root initiation", 21), ("Tillering / jointing", 45)],
    "sugarcane": [
        ("Basal / planting", 0),
        ("Tillering I", 45),
        ("Tillering II", 65),
        ("Earthing-up", 90),
    ],
    "rice": [("Basal / establishment", 0), ("Tillering", 25), ("Panicle initiation", 45)],
    "maize": [("Basal / sowing", 0), ("Knee-high stage", 25), ("Pre-tasseling", 45)],
}
STAGES_HI = {
    "Basal / sowing": "बुवाई के समय (आधार)",
    "Crown root initiation": "शिखर जड़ अवस्था (CRI)",
    "Tillering / jointing": "कल्ले / गाँठ बनना",
    "Basal / planting": "रोपाई के समय (आधार)",
    "Tillering I": "कल्ले निकलना I",
    "Tillering II": "कल्ले निकलना II",
    "Earthing-up": "मिट्टी चढ़ाना",
    "Basal / establishment": "रोपाई/स्थापना (आधार)",
    "Tillering": "कल्ले निकलना",
    "Panicle initiation": "बाली बनना शुरू",
    "Knee-high stage": "घुटने तक ऊँचाई",
    "Pre-tasseling": "नर मंजरी से पहले",
}
OFFSETS = {
    "sandy": (12, 6),
    "sandy-loam": (18, 12),
    "loam": (24, 12),
    "clay-loam": (30, 18),
    "clay": (36, 24),
}


def rain_risk(start: datetime, end: datetime, forecast: dict) -> tuple[str, float | None]:
    dates = []
    cursor = (start - timedelta(hours=24)).date()
    last = (end + timedelta(hours=24)).date()
    while cursor <= last:
        dates.append(cursor.isoformat())
        cursor += timedelta(days=1)
    rain = {day["date"]: day["rain_mm"] for day in forecast["days"]}
    # Daily totals conservatively cover the full application interval plus 24h each side.
    known_total = sum(rain.get(day, 0) for day in dates)
    if known_total > 20:
        return "high", known_total
    if forecast["status"] != "live" or any(day not in rain for day in dates):
        return "unknown", None
    return "lower", known_total


def application_schedule(inputs: AdvisoryInput, shopping: list[dict], forecast: dict) -> list[dict]:
    stages = STAGES[inputs.crop]
    urea = next(
        (row["apply_kg"] for row in shopping if row.get("id", row["product"].lower()) == "urea"),
        0.0,
    )
    other_n = sum(
        row["nutrients"]["N"] for row in shopping if row.get("id", row["product"].lower()) != "urea"
    )
    total_n = urea * 0.46 + other_n
    basal_urea = min(urea, max(0.0, total_n / len(stages) - other_n) / 0.46)
    topdress = (urea - basal_urea) / (len(stages) - 1)
    turn = inputs.irrigation_at
    if turn:
        turn = turn.replace(tzinfo=IST) if turn.tzinfo is None else turn.astimezone(IST)
    today = datetime.now(IST).date()
    result = []
    for index, (label, dap) in enumerate(stages):
        stage_date = inputs.sowing_date + timedelta(days=dap)
        earliest = latest = datetime.combine(stage_date, time(8), IST)
        turn_for_stage = None
        if index and turn:
            turn_for_stage = turn
            early, late = OFFSETS[inputs.texture]
            cycle = timedelta(days=inputs.irrigation_cycle_days)
            cycles = max(0, math.ceil((earliest + timedelta(hours=early) - turn_for_stage) / cycle))
            turn_for_stage += cycles * cycle
            earliest = turn_for_stage - timedelta(hours=early)
            latest = turn_for_stage - timedelta(hours=late)
        risk, rain = rain_risk(earliest, latest, forecast)
        allocations = {}
        for row in shopping:
            kg = (
                (basal_urea if index == 0 else topdress)
                if row.get("id", row["product"].lower()) == "urea"
                else (row["apply_kg"] if index == 0 else 0)
            )
            if kg > 1e-5:
                allocations[row["product"]] = kg
        notes = [
            "Provisional crop-stage dates; verify actual crop growth and soil moisture with an agronomist."
        ]
        if index and not turn:
            notes.append(
                "Canal roster unavailable. Confirm your water turn; no synchronized time can be recommended."
            )
        elif index:
            notes.append(
                "Uses your reported recurring water turn, not an official canal roster. Do not broadcast onto dry soil."
            )
        if earliest.date() < today:
            notes.append(
                "This date is past. Do not apply missed doses together; seek a revised plan."
            )
        if risk == "high":
            notes.append(
                "Heavy rain risk: HOLD application and reassess with an agronomist. The next cycle is not automatically safe."
            )
        elif risk == "unknown":
            notes.append(
                "Rain risk unknown or outside forecast horizon. Recheck weather 48 hours before application."
            )
        else:
            notes.append(
                "Lower modeled rain risk, not a safety guarantee. Recheck weather and avoid over-irrigation."
            )
        result.append(
            {
                "stage": label,
                "stage_hi": STAGES_HI[label],
                "dap": dap,
                "stage_date": stage_date.isoformat(),
                "start": earliest.isoformat(),
                "end": latest.isoformat(),
                "irrigation": turn_for_stage.isoformat() if turn_for_stage else None,
                "allocations": allocations,
                "risk": risk,
                "rain_mm": rain,
                "notes": notes,
            }
        )
    return result
