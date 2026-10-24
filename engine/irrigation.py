"""Season irrigation planner: FAO-56 soil-water balance with practical field quantities."""

import calendar
import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

UK_BIGHA_M2 = 632.29
ACRE_M2 = 4046.86


@lru_cache(maxsize=4)
def load_water_data(data_dir: Path) -> tuple[dict, dict]:
    water = json.loads((data_dir / "crop_water.json").read_text())
    climate = json.loads((data_dir / "climate_normals.json").read_text())
    return water, climate


def effective_rain_month(rain_mm: float) -> float:
    """FAO/CROPWAT dependable rainfall (≈80% probability) — plans for a moderately dry year."""
    if rain_mm <= 70:
        return max(0.0, 0.6 * rain_mm - 10)
    return 0.8 * rain_mm - 24


def daily_climate(day: date, climate: dict) -> tuple[float, float, float]:
    month = climate["months"][day.month - 1]
    days = calendar.monthrange(day.year, day.month)[1]
    return (
        month["et0_mm_day"],
        effective_rain_month(month["rain_mm"]) / days,
        month["rain_mm"] / days,
    )


def kc_at(day: int, crop: dict) -> float:
    ini, mid, end = crop["kc"]
    l_ini, l_dev, l_mid, l_late = crop["stages"]
    if day < l_ini:
        return ini
    if day < l_ini + l_dev:
        return ini + (mid - ini) * (day - l_ini) / l_dev
    if day < l_ini + l_dev + l_mid:
        return mid
    return mid + (end - mid) * min(1, (day - l_ini - l_dev - l_mid) / l_late)


def root_at(day: int, crop: dict) -> float:
    start, end = crop["root_m"]
    grow = crop["stages"][0] + crop["stages"][1]
    return start + (end - start) * min(1, day / grow)


def stage_name(day: int, crop: dict) -> tuple[str, str]:
    nearest = min(crop["critical"], key=lambda c: abs(c["das"] - day))
    if abs(nearest["das"] - day) <= 10:
        return nearest["en"], nearest["hi"]
    l_ini, l_dev, l_mid, _ = crop["stages"]
    if day < l_ini:
        return "Establishment", "स्थापना"
    if day < l_ini + l_dev:
        return "Vegetative growth", "बढ़वार"
    if day < l_ini + l_dev + l_mid:
        return "Mid-season (peak water use)", "मध्य अवस्था (अधिक पानी)"
    return "Maturity", "पकना"


def simulate_upland(
    crop: dict, sowing: date, awc: float, climate: dict, forced: list[int] | None = None
) -> dict:
    season = sum(crop["stages"])
    last_irrigation_day = season - crop["stop_days_before_harvest"]
    depletion = 0.0
    events, etc_total, rain_total, stress_days = [], 0.0, 0.0, 0
    anchors = {c["das"] for c in crop["critical"]} if crop.get("anchor_stages") else set()
    mandatory = {c["das"] for c in crop["critical"] if c.get("always")}
    last_event = -100
    for day in range(season):
        today = sowing + timedelta(days=day)
        et0, rain_eff, _ = daily_climate(today, climate)
        etc = kc_at(day, crop) * et0
        etc_total += etc
        rain_total += rain_eff
        taw = awc * root_at(day, crop)
        raw = crop["p"] * taw
        depletion = min(taw, max(0.0, depletion + etc - rain_eff))
        if depletion > raw and day <= last_irrigation_day:
            stress_days += 1
        if forced is not None:
            due = day in forced
        else:
            # Pre-sowing irrigation (palewa) is assumed; no irrigation during the first 15 days.
            due = day >= 15 and depletion >= raw
            # A recent irrigation already serves this stage; avoid back-to-back watering.
            recent = day - last_event < 7
            anchor_need = crop.get("anchor_min_depletion", 0.3) * taw
            if day in anchors and not recent and depletion >= anchor_need:
                due = True
            if day in mandatory and not recent:
                due = True
        if due and day <= last_irrigation_day and depletion > 1:
            events.append(
                {
                    "day": day,
                    "date": today,
                    "net_mm": depletion,
                    "taw_mm": taw,
                    "raw_mm": raw,
                    "root_cm": root_at(day, crop) * 100,
                }
            )
            depletion = 0.0
            last_event = day
        elif (
            forced is None
            and day in mandatory
            and day <= last_irrigation_day
            and day - last_event >= 7
        ):
            # Climatological rain is smeared over the month; real soil may still be dry at this stage.
            events.append(
                {
                    "day": day,
                    "date": today,
                    "net_mm": 0.3 * taw,
                    "taw_mm": taw,
                    "raw_mm": raw,
                    "root_cm": root_at(day, crop) * 100,
                    "conditional": True,
                }
            )
    return {
        "events": events,
        "etc_mm": etc_total,
        "rain_eff_mm": rain_total,
        "stress_days": stress_days,
        "season_days": season,
    }


def simulate_paddy(crop: dict, sowing: date, texture: str, climate: dict, awd: bool) -> dict:
    season = sum(crop["stages"])
    percolation = crop["percolation_mm_day"][texture]
    level, events, etc_total, rain_total, loss_total = 50.0, [], 0.0, 0.0, 0.0
    flower = crop["flowering_das"]
    land_prep = crop["land_preparation_mm"][texture]
    events.append(
        {"day": -1, "date": sowing - timedelta(days=1), "net_mm": land_prep, "label": "prep"}
    )
    for day in range(season):
        today = sowing + timedelta(days=day)
        et0, rain, _ = daily_climate(today, climate)
        etc = kc_at(day, crop) * et0
        perc = percolation if level > 0 else percolation * 0.3
        etc_total += etc
        rain_total += rain
        loss_total += etc + perc
        level = min(100.0, level - etc - perc + rain)
        if day >= season - crop["drain_days_before_harvest"]:
            continue
        keep_flooded = not awd or day < 14 or abs(day - flower) <= 7
        threshold = 0.0 if keep_flooded else -22.5
        if level <= threshold:
            events.append({"day": day, "date": today, "net_mm": 50 - level})
            level = 50.0
    return {
        "events": events,
        "etc_mm": etc_total,
        "rain_eff_mm": rain_total,
        "stress_days": 0,
        "season_days": season,
        "loss_mm": loss_total,
    }


def gross_mm(net: float, method: dict) -> float:
    return max(net / method["efficiency"], method["min_gross_mm"]) if net > 0 else 0.0


def field_quantities(gross: float, area_ha: float, flow_lps: float | None) -> dict:
    # Derive every quantity from the displayed depth so users can check the arithmetic.
    gross = round(gross, 1)
    m3 = gross * area_ha * 10
    return {
        "gross_mm": round(gross, 1),
        "gross_cm": round(gross / 10, 1),
        "volume_m3": round(m3, 1),
        "litres": round(m3 * 1000),
        "litres_per_bigha": round(gross * UK_BIGHA_M2),
        "litres_per_acre": round(gross * ACRE_M2),
        "pump_hours": round(m3 * 1000 / flow_lps / 3600, 2) if flow_lps else None,
    }


def plan_irrigation(
    crop_name: str,
    sowing: date,
    texture: str,
    area_ha: float,
    data_dir: Path,
    method_id: str | None = None,
    flow_lps: float | None = None,
    turn_hours: float | None = None,
    max_irrigations: int | None = None,
    forecast: dict | None = None,
) -> dict:
    water, climate = load_water_data(data_dir)
    crop = water["crops"][crop_name]
    method_id = method_id or crop["default_method"]
    methods = {k: v for k, v in water["methods"].items() if crop_name in v["crops"]}
    if method_id not in methods:
        raise ValueError(f"Irrigation method '{method_id}' does not suit {crop_name}.")
    method = methods[method_id]
    awc = water["awc_mm_per_m"][texture]
    notes_en, notes_hi = [], []
    limited = False

    if crop["kind"] == "paddy":
        sim = simulate_paddy(crop, sowing, texture, climate, awd=method_id == "rice_awd")
        comparison_sims = {
            mid: simulate_paddy(crop, sowing, texture, climate, awd=mid == "rice_awd")
            for mid in methods
        }
    else:
        sim = simulate_upland(crop, sowing, awc, climate)
        if max_irrigations is not None and len(sim["events"]) > max_irrigations:
            limited = True
            order = [crop["critical"][i]["das"] for i in crop["priority"]][:max_irrigations]
            sim = simulate_upland(crop, sowing, awc, climate, forced=sorted(order))
            notes_en.append(
                f"Only {max_irrigations} irrigation(s) available: scheduled at the most yield-critical stages. "
                f"Expect about {sim['stress_days']} days of water stress."
            )
            notes_hi.append(
                f"केवल {max_irrigations} सिंचाई उपलब्ध: सबसे ज़रूरी अवस्थाओं पर रखी गई। "
                f"लगभग {sim['stress_days']} दिन पानी की कमी रह सकती है।"
            )
        comparison_sims = {mid: sim for mid in methods}

    events = []
    for index, event in enumerate(sim["events"]):
        gross = gross_mm(event["net_mm"], method)
        if event.get("label") == "prep":
            stage_en, stage_hi = "Puddling / land preparation", "कद्दू / खेत की तैयारी"
            gross = event["net_mm"] / method["efficiency"]
        else:
            stage_en, stage_hi = stage_name(event["day"], crop)
        row = {
            "number": index + 1,
            "date": event["date"].isoformat(),
            "das": event["day"],
            "stage_en": stage_en,
            "stage_hi": stage_hi,
            "net_mm": round(event["net_mm"], 1),
            "root_cm": round(event.get("root_cm", 0)),
            **field_quantities(gross, area_ha, flow_lps),
            "conditional": event.get("conditional", False),
        }
        if forecast and forecast.get("status") == "live":
            window = {(event["date"] + timedelta(days=i)).isoformat() for i in range(3)}
            rain = sum(d["rain_mm"] for d in forecast["days"] if d["date"] in window)
            if any(d["date"] in window for d in forecast["days"]):
                row["forecast_rain_mm"] = round(rain, 1)
                row["postpone"] = rain >= max(10.0, event["net_mm"] * 0.5)
        if crop["kind"] == "upland" and gross > event["net_mm"] / method["efficiency"] + 0.5:
            row["over_minimum"] = True
        events.append(row)

    if crop["kind"] == "upland" and any(e.get("over_minimum") for e in events):
        notes_en.append(
            f"{method['en']} cannot apply less than ~{method['min_gross_mm'] / 10:g} cm evenly, more than early shallow roots can hold. "
            "Use smaller/shorter checks or a lighter method for early irrigations."
        )
        notes_hi.append(
            f"{method['hi']} से ~{method['min_gross_mm'] / 10:g} cm से कम पानी बराबर नहीं दिया जा सकता, जो शुरुआती जड़ें नहीं रोक पातीं। "
            "शुरुआती सिंचाई के लिए छोटी क्यारियाँ या हल्का तरीका अपनाएँ।"
        )
    if any(e["conditional"] for e in events):
        notes_en.append(
            "Conditional irrigation: winter rain usually keeps the soil moist at this stage. Irrigate only if there "
            "was no good rain (about 20 mm or more) in the previous 10 days and the khurpi test shows dry soil."
        )
        notes_hi.append(
            "शर्तिया सिंचाई: इस अवस्था में सर्दी की बारिश से मिट्टी अक्सर नम रहती है। पिछले 10 दिनों में अच्छी बारिश "
            "(लगभग 20 mm या अधिक) न हुई हो और खुरपी जाँच में मिट्टी सूखी हो, तभी सिंचाई करें।"
        )
    if crop["kind"] == "upland" and not events:
        notes_en.append(
            "In a normal monsoon this crop is largely rain-fed. Irrigate during dry spells of 7–10 days, especially at the critical stages listed."
        )
        notes_hi.append(
            "सामान्य मानसून में यह फसल ज़्यादातर बारिश से चलती है। 7–10 दिन सूखा रहे तो, खासकर ज़रूरी अवस्थाओं पर, सिंचाई करें।"
        )
    if texture == "sandy" and crop["kind"] == "upland":
        notes_en.append(
            "Sandy soil: irrigate lighter and more often; never apply urea before a heavy irrigation."
        )
        notes_hi.append("रेतीली मिट्टी: हल्की और जल्दी-जल्दी सिंचाई; भारी सिंचाई से पहले यूरिया न डालें।")
    if sowing < date.today() - timedelta(days=sum(crop["stages"])):
        notes_en.append("This season has ended; dates are for reference.")
        notes_hi.append("यह मौसम बीत चुका है; तारीखें केवल संदर्भ हेतु।")

    total_gross = sum(e["gross_mm"] for e in events)
    totals = field_quantities(total_gross, area_ha, flow_lps)
    largest = max((e["volume_m3"] for e in events if e["das"] >= 0), default=0)
    turn = None
    if turn_hours and flow_lps and largest:
        delivered = flow_lps * 3600 * turn_hours / 1000
        turn = {
            "delivered_m3": round(delivered, 1),
            "largest_event_m3": largest,
            "coverage": round(min(1.0, delivered / largest), 3),
            "hours_needed": round(largest * 1000 / flow_lps / 3600, 2),
        }

    comparison = []
    base_volume = None
    for mid, option in methods.items():
        option_sim = comparison_sims[mid]
        option_gross = sum(
            (e["net_mm"] / option["efficiency"])
            if e.get("label") == "prep"
            else gross_mm(e["net_mm"], option)
            for e in option_sim["events"]
        )
        volume = option_gross * area_ha * 10
        if mid in {"wild_flood", "rice_cf"}:
            base_volume = volume
        comparison.append(
            {
                "id": mid,
                "name_en": option["en"],
                "name_hi": option["hi"],
                "efficiency": option["efficiency"],
                "events": len(option_sim["events"]),
                "season_mm": round(option_gross),
                "season_m3": round(volume),
                "pump_hours": round(volume * 1000 / flow_lps / 3600, 1) if flow_lps else None,
                "pros_en": option["pros_en"],
                "pros_hi": option["pros_hi"],
                "cons_en": option["cons_en"],
                "cons_hi": option["cons_hi"],
                "selected": mid == method_id,
            }
        )
    for row in comparison:
        row["saving_pct"] = (
            round(100 * (1 - row["season_m3"] / base_volume)) if base_volume else None
        )
    comparison.sort(key=lambda r: r["season_m3"])

    paddy = crop["kind"] == "paddy"
    realtime = realtime_nowcast(crop, sowing, method, area_ha, flow_lps, climate, forecast)
    return {
        "crop": crop_name,
        "method": method_id,
        "method_en": method["en"],
        "method_hi": method["hi"],
        "efficiency": method["efficiency"],
        "texture": texture,
        "awc_mm_per_m": awc,
        "area_ha": area_ha,
        "events": events,
        "limited": limited,
        "realtime": realtime,
        "season": {
            "days": sim["season_days"],
            "crop_et_mm": round(sim["etc_mm"]),
            "effective_rain_mm": round(sim["rain_eff_mm"]),
            "net_mm": round(sum(e["net_mm"] for e in events)),
            "count": len(events),
            "stress_days": sim["stress_days"],
            **totals,
        },
        "turn": turn,
        "comparison": comparison,
        "notes_en": notes_en,
        "notes_hi": notes_hi,
        "critical": crop["critical"],
        "paddy": paddy,
        "how_en": paddy_rules_en() if paddy else upland_rules_en(),
        "how_hi": paddy_rules_hi() if paddy else upland_rules_hi(),
        "source": water["source"] + " Climate: " + climate["source"],
    }


def realtime_nowcast(
    crop: dict,
    sowing: date,
    method: dict,
    area_ha: float,
    flow_lps: float | None,
    climate: dict,
    forecast: dict | None,
) -> dict:
    """Compute next-7-day real-time water demand and irrigation dose from live Open-Meteo data."""
    today = date.today()
    if forecast and forecast.get("status") == "live" and forecast.get("days"):
        try:
            today = date.fromisoformat(str(forecast["days"][0]["date"]))
        except ValueError:
            pass
    das = max(0, min(sum(crop["stages"]) - 1, (today - sowing).days))
    kc = kc_at(das, crop)
    stage_en, stage_hi = stage_name(das, crop)
    live = bool(forecast and forecast.get("status") == "live" and forecast.get("days"))
    if live:
        assert forecast is not None
        days = forecast["days"][:7]
        rain_7d = sum(float(d.get("rain_mm", 0)) for d in days)
        rain_48h = sum(float(d.get("rain_mm", 0)) for d in days[:2])
        et0_7d = sum(
            float(d["et0_mm"])
            if "et0_mm" in d
            else daily_climate(today + timedelta(days=i), climate)[0]
            for i, d in enumerate(days)
        )
    else:
        rain_7d, rain_48h, et0_7d = 0.0, 0.0, 0.0
        for i in range(7):
            et0, rain_eff, _ = daily_climate(today + timedelta(days=i), climate)
            et0_7d += et0
            rain_7d += rain_eff
    crop_etc_7d = round(et0_7d * kc, 1)
    eff_rain_7d = round(min(rain_7d * 0.8, crop_etc_7d), 1)
    net_need_mm = round(max(0.0, crop_etc_7d - eff_rain_7d), 1)
    gross = gross_mm(net_need_mm, method) if net_need_mm > 2 else 0.0
    quantities = field_quantities(gross, area_ha, flow_lps)
    if rain_48h >= 15:
        action = "wait_rain"
        advice_en = (
            f"POSTPONE IRRIGATION: {rain_48h:.1f} mm rain is forecast in the next 48 hours. "
            "Let rain wet the root zone and hold urea until after heavy rain."
        )
        advice_hi = (
            f"सिंचाई रोकें: अगले 48 घंटों में {rain_48h:.1f} mm बारिश का अनुमान है। "
            "बारिश का लाभ लें और भारी बारिश से पहले यूरिया न डालें।"
        )
    elif net_need_mm <= 5:
        action = "moist"
        advice_en = (
            f"Weather demand is low ({crop_etc_7d:.1f} mm crop water use vs {rain_7d:.1f} mm rain). "
            "Irrigate only if the khurpi test shows dry soil at root depth."
        )
        advice_hi = (
            f"मौसम की जल माँग कम है ({crop_etc_7d:.1f} mm फसल उपयोग बनाम {rain_7d:.1f} mm बारिश)। "
            "केवल तभी सिंचाई करें जब खुरपी जाँच में जड़ के पास मिट्टी सूखी हो।"
        )
    else:
        action = "irrigate_when_due"
        advice_en = (
            f"7-day live crop water demand is {crop_etc_7d:.1f} mm (Kc={kc:.2f}) with {rain_7d:.1f} mm forecast rain. "
            f"If irrigating this week via {method['en']}, apply ~{quantities['gross_cm']} cm "
            f"({quantities['litres_per_bigha']:,} L/bigha, {quantities['volume_m3']:.0f} m³ total)."
        )
        advice_hi = (
            f"अगले 7 दिन फसल की जल माँग {crop_etc_7d:.1f} mm (Kc={kc:.2f}) और बारिश अनुमान {rain_7d:.1f} mm है। "
            f"यदि इस सप्ताह {method['hi']} से सिंचाई करें, तो ~{quantities['gross_cm']} cm "
            f"({quantities['litres_per_bigha']:,} लीटर/बीघा, कुल {quantities['volume_m3']:.0f} m³) पानी दें।"
        )
    return {
        "live": live,
        "das": das,
        "stage_en": stage_en,
        "stage_hi": stage_hi,
        "kc": round(kc, 2),
        "et0_7d_mm": round(et0_7d, 1),
        "crop_etc_7d_mm": crop_etc_7d,
        "rain_48h_mm": round(rain_48h, 1),
        "rain_7d_mm": round(rain_7d, 1),
        "net_deficit_7d_mm": net_need_mm,
        "action": action,
        "advice_en": advice_en,
        "advice_hi": advice_hi,
        **quantities,
    }


def upland_rules_en() -> list[str]:
    return [
        "Stop inflow when water has covered about 80–85% of the check/furrow length; the rest spreads by itself.",
        "Do not keep water standing for more than a few hours (except paddy).",
        "Before irrigating, check moisture at root depth with a khurpi: if the soil still forms a ball when squeezed, wait.",
        "24 hours after irrigation the soil should be moist down to the root depth shown — wetter than that means water and urea were lost below the roots.",
        "Apply urea on moist soil just before (or with) the irrigation, never just before heavy rain.",
    ]


def upland_rules_hi() -> list[str]:
    return [
        "जब पानी क्यारी/नाली की लगभग 80–85% लंबाई तक पहुँचे, तब पानी बंद करें; बाकी अपने आप फैल जाएगा।",
        "कुछ घंटों से ज़्यादा पानी खड़ा न रखें (धान को छोड़कर)।",
        "सिंचाई से पहले खुरपी से जड़ की गहराई पर नमी देखें: मिट्टी दबाने पर गोला बने तो रुकें।",
        "सिंचाई के 24 घंटे बाद मिट्टी बताई गई जड़ गहराई तक नम होनी चाहिए — उससे ज़्यादा गीली हो तो पानी और यूरिया जड़ों से नीचे बह गए।",
        "यूरिया नम मिट्टी पर सिंचाई से ठीक पहले डालें, भारी बारिश से ठीक पहले कभी नहीं।",
    ]


def paddy_rules_en() -> list[str]:
    return [
        "Keep 2–5 cm water for the first two weeks after transplanting.",
        "AWD: install a perforated 30 cm tube (15 cm below ground). Re-flood to 5 cm when water in the tube drops 15 cm below the surface.",
        "Keep the field flooded from one week before to one week after flowering.",
        "Drain the field 10–15 days before harvest.",
        "Apply urea into 2–3 cm standing water or just before re-flooding, not into deep water that will overflow.",
    ]


def paddy_rules_hi() -> list[str]:
    return [
        "रोपाई के बाद पहले दो सप्ताह 2–5 cm पानी रखें।",
        "AWD: 30 cm की छेद वाली नली (15 cm ज़मीन के अंदर) लगाएँ। नली में पानी सतह से 15 cm नीचे जाए तो 5 cm तक पानी भरें।",
        "फूल आने से एक सप्ताह पहले से एक सप्ताह बाद तक खेत में पानी भरा रखें।",
        "कटाई से 10–15 दिन पहले पानी निकाल दें।",
        "यूरिया 2–3 cm खड़े पानी में या पानी भरने से ठीक पहले डालें, गहरे बहते पानी में नहीं।",
    ]
