import hashlib
import hmac
import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from pydantic import ValidationError

from bot.formatter import format_result_hindi
from bot.parser import (
    decipher_voice_utterance,
    normalize,
    parse_area,
    parse_crop,
    parse_number,
    parse_soil,
    parse_spoken_budget,
    parse_yes_no,
)
from engine.models import BLOCKS, AdvisoryInput
from engine.service import (
    build_advisory,
    load_blocks,
    resolve_soil_profile,
    suggested_budget_rs,
)
from storage import get_report, save_report

PROMPTS = {
    "BLOCK": (
        "🌾 *जल-खाद* में स्वागत है! (शोध प्रोटोटाइप — खेत में उपयोग से पहले KVK/विशेषज्ञ से जाँच कराएँ)\n\n"
        "अपना *ब्लॉक* चुनें (नंबर भेजें या बोलें 🎤):\n"
        "1️⃣ रुड़की (Roorkee)\n"
        "2️⃣ भगवानपुर (Bhagwanpur)\n"
        "3️⃣ लक्सर (Laksar)\n"
        "4️⃣ नारसन (Narsan)\n"
        "5️⃣ बहादराबाद (Bahadrabad)\n"
        "6️⃣ खानपुर (Khanpur)\n\n"
        '💡 _आप सीधे पूरा वाक्य भी बोल या लिख सकते हैं, जैसे: "रुड़की ढंडेरा 5 बीघा गेहूं बजट 2500"_'
    ),
    "VILLAGE": "गाँव का नाम लिखें। (या नीचे दिए गए नंबर 1–6 में से चुनें; GPS, मौसम व मिट्टी अपने-आप जुड़ेंगे)",
    "CROP": "फसल चुनें:\n1️⃣ गेहूं (Wheat)\n2️⃣ गन्ना (Sugarcane)\n3️⃣ धान (Rice)\n4️⃣ मक्का (Maize)",
    "AREA": (
        "खेत का क्षेत्र भेजें (जैसे *5 bigha*, *2 बीघा*, *1 acre*, या *0.5 ha*):\n"
        "• उत्तराखंड बीघा (~632 m²) अपने-आप गिना जाएगा।"
    ),
    "SOWING": "बुवाई की तारीख YYYY-MM-DD में भेजें, जैसे 2026-11-01।",
    "TEXTURE": "मिट्टी: 1 रेतीली, 2 बलुई दोमट, 3 दोमट, 4 चिकनी दोमट, 5 चिकनी।",
    "IRRIGATION": "अगले पानी की तारीख/समय IST में YYYY-MM-DD HH:MM भेजें, या 'नहीं'। यह आधिकारिक नहर समय नहीं है।",
    "CYCLE": "पानी कितने दिन बाद दोबारा आता है? 1–30 के बीच अंक भेजें।",
    "COORDINATES": "मौसम के लिए latitude,longitude भेजें (जैसे 29.85,77.88), या 'नहीं'।",
    "BUDGET": (
        "पूरे खेत का खाद *बजट (₹)* लिखें या बोलें (जैसे *2000* या *दो हज़ार*):\n"
        "• मौसम, मिट्टी का प्रकार और सिंचाई अपने-आप जोड़ लिए गए हैं।"
    ),
    "SOIL": (
        "क्या आपके पास अपना *मृदा स्वास्थ्य कार्ड (SHC)* है?\n"
        "1️⃣ हाँ — मेरे पास कार्ड के N, P, K नंबर हैं\n"
        "2️⃣ नहीं — सामान्य/संदर्भ सलाह बनाएँ\n"
        "3️⃣ गाँव/ब्लॉक की सरकारी मिट्टी जाँच (KVK/CAO) से स्वतः भरें ✨"
    ),
    "SOIL_BASIS": (
        "कार्ड की इकाई kg/ha होनी चाहिए। 1 N,P,K (तत्व), 2 N,P2O5,K2O (ऑक्साइड)। "
        "(या सीधे N,P,K भेजें जैसे 180,45,220)। ppm वाले कार्ड के लिए विशेषज्ञ से रूपांतरण कराएँ।"
    ),
    "SOIL_DATA": "तीन मान N,P,K (चुनी गई इकाई में) भेजें, जैसे 180,45,220।",
    "RESULT": (
        "1 PDF | 2 मौसम अलर्ट (सहमति: फोन/निर्देशांक सहेजें) | 3 फिर शुरू | 4 वैज्ञानिक आधार\n"
        "STOP अलर्ट बंद | DELETE बॉट डेटा मिटाएँ"
    ),
}

NEXT_REQUIRED_STEP = ("BLOCK", "VILLAGE", "CROP", "AREA", "BUDGET", "SOIL")


def session_key(identity: str, secret: str) -> str:
    return hmac.new(secret.encode(), identity.encode(), hashlib.sha256).hexdigest()


def prompt_for_state(state: dict, data_dir: Path) -> str:
    step = state["step"]
    values = state.get("inputs", {})
    blocks_data = load_blocks(data_dir)["blocks"]
    if step == "VILLAGE" and values.get("block") in blocks_data:
        villages = blocks_data[values["block"]].get("villages", [])
        v_lines = "\n".join(f"{i + 1}️⃣ {v['hi']} ({v['name']})" for i, v in enumerate(villages[:6]))
        return (
            f"📍 ब्लॉक: *{blocks_data[values['block']]['hi']}* ✅\n\n"
            f"गाँव का नाम लिखें। या नंबर चुनें:\n{v_lines}\n"
            "_(गाँव चुनते ही GPS, मौसम और मिट्टी डेटा अपने-आप आ जाएगा)_"
        )
    if step == "BUDGET" and values.get("crop") and values.get("area"):
        area_ha = AdvisoryInput(
            block=values.get("block", "Roorkee"),
            village=values.get("village", "Dhandera"),
            crop=values["crop"],
            sowing_date=values.get("sowing_date") or date.today().isoformat(),
            area=values["area"],
            area_unit=values.get("area_unit", "ha"),
            bigha_m2=values.get("bigha_m2", 632.29) if values.get("area_unit") == "bigha" else None,
            budget=1000,
        ).area_ha
        suggested = int(suggested_budget_rs(values["crop"], area_ha))
        return (
            f"{PROMPTS['BUDGET']}\n"
            f"💡 आपके खेत के लिए सुझाया बजट: *₹{suggested}* (सीधे *{suggested}* भेजें या अपनी राशि लिखें)"
        )
    return PROMPTS[step]


def quick_options_for_state(state: dict, data_dir: Path) -> list[dict]:
    step = state["step"]
    values = state.get("inputs", {})
    blocks_data = load_blocks(data_dir)["blocks"]
    if step == "BLOCK":
        return [
            {"label": f"{i + 1} {blocks_data[b]['hi']}", "value": str(i + 1)}
            for i, b in enumerate(BLOCKS)
        ]
    if step == "VILLAGE":
        villages = blocks_data.get(values.get("block", "Roorkee"), {}).get("villages", [])
        return [
            {"label": f"{i + 1} {v['hi']}", "value": str(i + 1)} for i, v in enumerate(villages[:6])
        ]
    if step == "CROP":
        return [
            {"label": "1 गेहूं (Wheat)", "value": "1"},
            {"label": "2 गन्ना (Sugarcane)", "value": "2"},
            {"label": "3 धान (Rice)", "value": "3"},
            {"label": "4 मक्का (Maize)", "value": "4"},
        ]
    if step == "AREA":
        return [
            {"label": "2 बीघा", "value": "2 bigha"},
            {"label": "5 बीघा", "value": "5 bigha"},
            {"label": "10 बीघा", "value": "10 bigha"},
            {"label": "1 एकड़", "value": "1 acre"},
            {"label": "1 हेक्टेयर", "value": "1 ha"},
        ]
    if step == "BUDGET":
        return [
            {"label": "₹1,500", "value": "1500"},
            {"label": "₹2,000", "value": "2000"},
            {"label": "₹3,000", "value": "3000"},
            {"label": "₹5,000", "value": "5000"},
        ]
    if step == "SOIL":
        return [
            {"label": "3 ✨ सरकारी मिट्टी जाँच स्वतः लें", "value": "3"},
            {"label": "2 कार्ड नहीं (सामान्य)", "value": "2"},
            {"label": "1 मेरा कार्ड है", "value": "1"},
        ]
    if step == "SOIL_BASIS":
        return [
            {"label": "1 तत्व (N, P, K)", "value": "1"},
            {"label": "2 ऑक्साइड (N, P2O5, K2O)", "value": "2"},
        ]
    if step == "SOIL_DATA":
        return [
            {"label": "उदाहरण: 180,35,240", "value": "180,35,240"},
            {"label": "उदाहरण: 210,18,190", "value": "210,18,190"},
        ]
    if step == "RESULT":
        return [
            {"label": "1 📄 हिंदी PDF कार्ड", "value": "1"},
            {"label": "2 🌧️ मौसम अलर्ट", "value": "2"},
            {"label": "3 🔄 फिर से शुरू", "value": "3"},
            {"label": "4 ℹ️ वैज्ञानिक आधार", "value": "4"},
        ]
    return []


def apply_village_autofill(db: sqlite3.Connection, values: dict, data_dir: Path) -> dict:
    """Automatically fill GPS coordinates, soil texture, sowing date, and water defaults for the village."""
    block = values.get("block", "Roorkee")
    village = values.get("village", "Dhandera")
    blocks_data = load_blocks(data_dir)
    for v in blocks_data["blocks"].get(block, {}).get("villages", []):
        if village.lower() in {v["name"].lower(), v["hi"].lower()}:
            values["village"] = v["name"]
            values.setdefault("latitude", v["lat"])
            values.setdefault("longitude", v["lon"])
            values.setdefault("texture", v.get("texture", "sandy-loam"))
            break
    if "latitude" not in values:
        b_info = blocks_data["blocks"].get(block, blocks_data["blocks"]["Roorkee"])
        values["latitude"] = b_info["lat"]
        values["longitude"] = b_info["lon"]
        values.setdefault("texture", b_info.get("default_texture", "sandy-loam"))
    soil_prof = resolve_soil_profile(block, values["village"], data_dir, db=db)
    values.setdefault("texture", soil_prof.get("texture", "sandy-loam"))
    values.setdefault("sowing_date", date.today().isoformat())
    values.setdefault("flow_lps", 10.0)
    values.setdefault("turn_hours", 4.0)
    return soil_prof


def resume_prompt(db: sqlite3.Connection, identity: str, secret: str, base_url: str) -> str:
    row = db.execute(
        "SELECT * FROM bot_sessions WHERE session_key=?", (session_key(identity, secret),)
    ).fetchone()
    if row and datetime.now(timezone.utc) - datetime.fromisoformat(row["updated_at"]) <= timedelta(
        minutes=30
    ):
        state = json.loads(row["payload"])
        if state["step"] == "RESULT" and (report := get_report(db, state["report_id"])):
            return format_result_hindi(report, base_url)
        return PROMPTS[state["step"]]
    return "नमस्ते! बातचीत शुरू करने के लिए “नमस्ते” भेजें या माइक 🎤 दबाकर बोलें। यह परीक्षण मॉडल है; उपयोग से पहले कृषि विशेषज्ञ से जाँच जरूरी है।"


def handle_message(
    db: sqlite3.Connection,
    identity: str,
    text: str,
    secret: str,
    data_dir: Path,
    base_url: str,
    weather_enabled: bool = False,
    alerts_enabled: bool = False,
    real_phone: str | None = None,
) -> dict:
    key = session_key(identity, secret)
    now = datetime.now(timezone.utc)
    text = text.strip()
    normalized = normalize(text)
    if normalized in {"stop", "बंद", "delete"}:
        db.execute("DELETE FROM subscriptions WHERE session_key = ?", (key,))
        if normalized == "delete":
            row = db.execute(
                "SELECT payload FROM bot_sessions WHERE session_key = ?", (key,)
            ).fetchone()
            if row:
                for report_id in json.loads(row["payload"]).get("report_ids", []):
                    db.execute("DELETE FROM recommendations WHERE id = ?", (report_id,))
            db.execute("DELETE FROM bot_sessions WHERE session_key = ?", (key,))
        return {
            "text": "अलर्ट बंद हैं। DELETE पर सहेजा गया बॉट सत्र और उससे जुड़ी उपलब्ध रिपोर्ट भी मिटा दी गई हैं।",
            "step": "BLOCK",
            "options": quick_options_for_state({"step": "BLOCK", "inputs": {}}, data_dir),
        }
    row = db.execute("SELECT * FROM bot_sessions WHERE session_key = ?", (key,)).fetchone()
    expired = row and now - datetime.fromisoformat(row["updated_at"]) > timedelta(minutes=30)

    # Check if the farmer spoke/typed a rich multi-entity sentence right at the start!
    blocks_data = load_blocks(data_dir)
    spoken = decipher_voice_utterance(text, blocks_data)
    entity_count = sum(1 for k in ("block", "village", "crop", "area", "budget") if k in spoken)

    if (not row or expired or normalized in {"restart", "शुरू"}) and entity_count < 2:
        previous = json.loads(row["payload"]) if row else {}
        state = {
            "step": "BLOCK",
            "inputs": {},
            "errors": 0,
            "report_ids": previous.get("report_ids", []),
        }
        reply = {"text": PROMPTS["BLOCK"]}
    else:
        if not row or expired:
            state = {"step": "BLOCK", "inputs": {}, "errors": 0, "report_ids": []}
        else:
            state = json.loads(row["payload"])
        try:
            if entity_count >= 2 and state["step"] != "RESULT":
                reply = fast_forward_from_speech(
                    db, state, spoken, data_dir, base_url, weather_enabled
                )
            else:
                reply = advance(db, state, normalized, text, data_dir, base_url, weather_enabled)
            if reply.pop("subscribe", False):
                values = state["inputs"]
                if not alerts_enabled or not real_phone or values.get("latitude") is None:
                    reply["text"] = (
                        "अलर्ट चालू नहीं हुए: प्रदाता/टेम्पलेट, लाइव मौसम और सही निर्देशांक जरूरी हैं। वेब पर मौसम जाँचें।"
                    )
                else:
                    db.execute(
                        "INSERT INTO subscriptions VALUES (?, ?, ?, ?, ?, NULL) "
                        "ON CONFLICT(session_key) DO UPDATE SET phone=excluded.phone, "
                        "latitude=excluded.latitude, longitude=excluded.longitude, consent_at=excluded.consent_at",
                        (key, real_phone, values["latitude"], values["longitude"], now.isoformat()),
                    )
                    reply["text"] = (
                        "सहमति दर्ज: फोन/निर्देशांक अलर्ट के लिए सहेजे गए। रोज 7 बजे भारी बारिश की जाँच होगी; सूचना डिलीवरी सुनिश्चित नहीं है। STOP से बंद करें।"
                    )
            state["errors"] = 0
        except (ValueError, ValidationError) as exc:
            state["errors"] = state.get("errors", 0) + 1
            message = (
                "मान सही सीमा/प्रारूप में नहीं है।" if isinstance(exc, ValidationError) else str(exc)
            )
            reply = {"text": f"{message}\n{prompt_for_state(state, data_dir)}"}
            if state["errors"] >= 3:
                reply["text"] += "\nसहायता: ऊपर दिया उदाहरण देखें, या restart भेजें।"

    reply["step"] = state["step"]
    reply["options"] = quick_options_for_state(state, data_dir)
    reply["inputs"] = state.get("inputs", {})
    db.execute(
        "INSERT INTO bot_sessions VALUES (?, ?, ?) ON CONFLICT(session_key) "
        "DO UPDATE SET updated_at=excluded.updated_at, payload=excluded.payload",
        (key, now.isoformat(), json.dumps(state, ensure_ascii=False)),
    )
    return reply


def fast_forward_from_speech(
    db: sqlite3.Connection,
    state: dict,
    spoken: dict,
    data_dir: Path,
    base_url: str,
    weather_enabled: bool,
) -> dict:
    """Fill multiple spoken fields at once and jump to the next missing step or result."""
    values = state["inputs"]
    for k in (
        "block",
        "village",
        "crop",
        "area",
        "area_unit",
        "bigha_m2",
        "budget",
        "latitude",
        "longitude",
        "texture",
    ):
        if k in spoken:
            values[k] = spoken[k]
    if "block" in values and "village" not in values:
        v_list = load_blocks(data_dir)["blocks"][values["block"]].get("villages", [])
        if v_list:
            values["village"] = v_list[0]["name"]
    if "block" in values and "village" in values:
        soil_prof = apply_village_autofill(db, values, data_dir)
    else:
        soil_prof = None
    if "soil_npk" in spoken:
        n, p, k = spoken["soil_npk"]
        values["soil"] = {"N": n, "P": p, "K": k, "basis": "elemental"}
        values["soil_source"] = "card"
    for step_name, key_name in (
        ("BLOCK", "block"),
        ("VILLAGE", "village"),
        ("CROP", "crop"),
        ("AREA", "area"),
        ("BUDGET", "budget"),
    ):
        if key_name not in values:
            state["step"] = step_name
            return {
                "text": f"🎤 समझा गया: {_spoken_summary_hi(values)}\n\n{prompt_for_state(state, data_dir)}"
            }
    if "soil" not in values and soil_prof is not None:
        values["soil"] = soil_prof["soil"]
        values["soil_source"] = soil_prof["tier"]
    return finish(db, state, data_dir, base_url, weather_enabled)


def _spoken_summary_hi(values: dict) -> str:
    parts = []
    if "block" in values:
        parts.append(f"ब्लॉक: {values['block']}")
    if "village" in values:
        parts.append(f"गाँव: {values['village']}")
    if "crop" in values:
        parts.append(f"फसल: {values['crop']}")
    if "area" in values:
        parts.append(f"क्षेत्र: {values['area']} {values.get('area_unit', 'ha')}")
    if "budget" in values:
        parts.append(f"बजट: ₹{values['budget']:.0f}")
    return " | ".join(parts)


def advance(
    db: sqlite3.Connection,
    state: dict,
    normalized: str,
    text: str,
    data_dir: Path,
    base_url: str,
    weather_enabled: bool,
) -> dict:
    step = state["step"]
    values = state["inputs"]
    blocks_data = load_blocks(data_dir)
    if step == "BLOCK":
        if normalized in {str(i) for i in range(1, 7)}:
            values["block"] = BLOCKS[int(normalized) - 1]
        elif normalized in {b.lower() for b in BLOCKS}:
            values["block"] = next(b for b in BLOCKS if b.lower() == normalized)
        else:
            spoken = decipher_voice_utterance(text, blocks_data)
            if "block" in spoken:
                values["block"] = spoken["block"]
            else:
                raise ValueError("ब्लॉक का नंबर 1–6 भेजें या नाम बोलें।")
        state["step"] = "VILLAGE"
    elif step == "VILLAGE":
        villages = blocks_data["blocks"].get(values.get("block", "Roorkee"), {}).get("villages", [])
        if normalized.isdigit() and 1 <= int(normalized) <= len(villages):
            chosen = villages[int(normalized) - 1]
            values["village"] = chosen["name"]
        elif 1 <= len(text) <= 80:
            values["village"] = text
        else:
            raise ValueError("गाँव का नाम 1–80 अक्षर में दें।")
        apply_village_autofill(db, values, data_dir)
        state["step"] = "CROP"
    elif step == "CROP":
        values["crop"] = parse_crop(text)
        state["step"] = "AREA"
    elif step == "AREA":
        values.update(parse_area(text))
        state["step"] = "BUDGET"
    elif step == "SOWING":
        values["sowing_date"] = date.fromisoformat(normalized).isoformat()
        state["step"] = "TEXTURE"
    elif step == "TEXTURE":
        if normalized not in {"1", "2", "3", "4", "5"}:
            raise ValueError("मिट्टी का नंबर 1–5 भेजें।")
        values["texture"] = ("sandy", "sandy-loam", "loam", "clay-loam", "clay")[
            int(normalized) - 1
        ]
        state["step"] = "IRRIGATION"
    elif step == "IRRIGATION":
        if normalized in {"no", "नहीं", "nahi", "skip"}:
            state["step"] = "COORDINATES"
        else:
            values["irrigation_at"] = datetime.strptime(normalized, "%Y-%m-%d %H:%M").isoformat()
            state["step"] = "CYCLE"
    elif step == "CYCLE":
        if not normalized.isdigit() or not 1 <= int(normalized) <= 30:
            raise ValueError("चक्र 1–30 दिन होना चाहिए।")
        values["irrigation_cycle_days"] = int(normalized)
        state["step"] = "COORDINATES"
    elif step == "COORDINATES":
        if normalized not in {"no", "नहीं", "nahi", "skip"}:
            pieces = normalized.split(",")
            if len(pieces) != 2:
                raise ValueError("latitude,longitude भेजें या नहीं लिखें।")
            lat, lon = map(float, pieces)
            if not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise ValueError("निर्देशांक गलत हैं।")
            values.update(latitude=lat, longitude=lon)
        state["step"] = "BUDGET"
    elif step == "BUDGET":
        # Support legacy full-flow scripts that send an ISO sowing date right after AREA
        if len(normalized) == 10 and normalized[4:5] == "-" and normalized[7:8] == "-":
            values["sowing_date"] = date.fromisoformat(normalized).isoformat()
            state["step"] = "TEXTURE"
            return {"text": prompt_for_state(state, data_dir)}
        budget = parse_spoken_budget(text)
        if budget is None:
            budget = parse_number(text)
        if budget > 1000000:
            raise ValueError("बजट अधिकतम ₹10,00,000 है।")
        values["budget"] = budget
        state["step"] = "SOIL"
    elif step == "SOIL":
        if normalized == "3" or "सरकारी" in normalized or "auto" in normalized:
            soil_prof = resolve_soil_profile(
                values.get("block", "Roorkee"), values.get("village"), data_dir, db=db
            )
            values["soil"] = soil_prof["soil"]
            values["soil_source"] = soil_prof["tier"]
            return finish(db, state, data_dir, base_url, weather_enabled)
        if parse_yes_no(text):
            state["step"] = "SOIL_BASIS"
        else:
            return finish(db, state, data_dir, base_url, weather_enabled)
    elif step == "SOIL_BASIS":
        # Allow farmer to send N,P,K directly without extra basis step
        try:
            n, p, k = parse_soil(text)
            values["soil"] = {"N": n, "P": p, "K": k, "basis": "elemental"}
            values["soil_source"] = "card"
            return finish(db, state, data_dir, base_url, weather_enabled)
        except ValueError:
            pass
        if normalized not in {"1", "2"}:
            raise ValueError("इकाई का नंबर 1 या 2 भेजें (या सीधे N,P,K लिखें)।")
        state["soil_basis"] = "elemental" if normalized == "1" else "oxide"
        state["step"] = "SOIL_DATA"
    elif step == "SOIL_DATA":
        n, p, k = parse_soil(text)
        values["soil"] = {"N": n, "P": p, "K": k, "basis": state.get("soil_basis", "elemental")}
        values["soil_source"] = "card"
        return finish(db, state, data_dir, base_url, weather_enabled)
    elif step == "RESULT":
        if normalized == "1":
            if get_report(db, state["report_id"]) is None:
                raise ValueError("रिपोर्ट अब उपलब्ध नहीं है; restart करें।")
            return {
                "text": "यह परीक्षण PDF है; कृषि विशेषज्ञ से जाँच कराएँ।",
                "document": f"{base_url}/results/{state['report_id']}/pdf?lang=hi",
            }
        if normalized == "2":
            return {"subscribe": True}
        if normalized == "3":
            state.update(step="BLOCK", inputs={}, errors=0)
        elif normalized == "4":
            return {
                "text": (
                    "वैज्ञानिक आधार: (1) गाँव/ब्लॉक की मिट्टी जाँच (KVK धनौरी / पचौरी आदि 2023, n=300) "
                    "या किसान के कार्ड के अनुसार खुराक को कम/मध्यम/अधिक (125%/100%/75%) किया जाता है। "
                    "(2) PuLP बजट में पूर्ण बोरियाँ चुनता है। "
                    "(3) सिंचाई के लिए रुड़की के 10-वर्षीय जलवायु डेटा + लाइव Open-Meteo मौसम (ET0 व बारिश) से पानी की मात्रा (लीटर/बीघा व cm) निकाली जाती है।"
                )
            }
        else:
            if normalized != "3":
                raise ValueError("विकल्प 1–4 भेजें।")
    return {"text": prompt_for_state(state, data_dir)}


def finish(
    db: sqlite3.Connection, state: dict, data_dir: Path, base_url: str, weather_enabled: bool
) -> dict:
    values = state["inputs"]
    values.setdefault("sowing_date", date.today().isoformat())
    inputs = AdvisoryInput.model_validate(values)
    report = save_report(db, build_advisory(inputs, data_dir, weather_enabled))
    state["step"], state["report_id"] = "RESULT", report["id"]
    state.setdefault("report_ids", []).append(report["id"])
    return {"text": format_result_hindi(report, base_url), "report_id": report["id"]}
