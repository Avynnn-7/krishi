import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from engine.irrigation import plan_irrigation
from engine.models import NUTRIENTS, AdvisoryInput, Product, Soil
from engine.optimizer import optimize
from engine.recommendations import build_recommendations
from engine.soil_card import interpret_soil
from engine.stcr import load_profiles, nutrient_requirement
from engine.timing import application_schedule
from engine.weather import get_forecast, resolve_location

SEASONS = {
    "wheat": [((10, 25), (12, 10), "Timely to moderately late wheat sowing window.")],
    "rice": [((6, 10), (7, 25), "Kharif transplanting window.")],
    "sugarcane": [((2, 10), (4, 15), "Spring planting."), ((9, 20), (11, 5), "Autumn planting.")],
    "maize": [((6, 10), (7, 20), "Kharif sowing."), ((1, 25), (3, 20), "Spring sowing.")],
}


@lru_cache(maxsize=4)
def load_catalog_cached(data_dir: Path) -> tuple[tuple[Product, ...], str]:
    catalog = json.loads((data_dir / "fertilizer_catalog.json").read_text())
    products = tuple(Product.model_validate(p) for p in catalog["products"])
    if len({p.id for p in products}) != len(products):
        raise ValueError("Duplicate fertilizer product IDs.")
    return products, catalog["source"]


def load_catalog(data_dir: Path) -> tuple[list[Product], str]:
    products, source = load_catalog_cached(data_dir)
    return [p.model_copy() for p in products], source


@lru_cache(maxsize=4)
def load_blocks(data_dir: Path) -> dict:
    return json.loads((data_dir / "blocks.json").read_text())


@lru_cache(maxsize=4)
def load_soil_baselines(data_dir: Path) -> dict:
    return json.loads((data_dir / "soil_averages.json").read_text())


SOIL_VALUE_KEYS = (
    "N",
    "P",
    "K",
    "basis",
    "ph",
    "ec",
    "organic_carbon",
    "sulphur",
    "zinc",
    "iron",
    "manganese",
    "copper",
    "boron",
)


def resolve_soil_profile(block: str, village: str | None, data_dir: Path, db=None) -> dict:
    """Return the best available soil profile: uploaded official village lab record -> village baseline -> published block baseline."""
    baselines = load_soil_baselines(data_dir)
    if db is not None and village:
        from storage import find_village_soil

        uploaded = find_village_soil(db, block, village)
        if uploaded:
            soil_dict = {
                k: uploaded[k] for k in SOIL_VALUE_KEYS if k in uploaded and uploaded[k] is not None
            }
            soil_dict.setdefault("basis", "elemental")
            return {
                "tier": "official_village",
                "tier_label_en": f"Official Village Soil Test Record ({uploaded['village']}, n={uploaded.get('samples', 1)})",
                "tier_label_hi": f"आधिकारिक गाँव मिट्टी जाँच रिकॉर्ड ({uploaded.get('village_hi') or uploaded['village']}, n={uploaded.get('samples', 1)})",
                "source": uploaded.get(
                    "source", "Agricultural Testing Official / Village SHC Survey"
                ),
                "tested_date": uploaded.get("tested_date"),
                "samples": uploaded.get("samples", 1),
                "texture": uploaded.get("texture", "sandy-loam"),
                "soil": Soil.model_validate(soil_dict).model_dump(mode="json"),
            }
    v_norm = (village or "").strip().lower()
    if v_norm:
        for item in baselines.get("village_overrides", []):
            if v_norm in {item["village"].lower(), item.get("village_hi", "").lower()}:
                soil_dict = {
                    k: item[k] for k in SOIL_VALUE_KEYS if k in item and item[k] is not None
                }
                soil_dict.setdefault("basis", "elemental")
                return {
                    "tier": "official_village",
                    "tier_label_en": f"Village Soil Survey Cluster ({item['village']}, n={item.get('samples', 10)})",
                    "tier_label_hi": f"गाँव मिट्टी जाँच क्लस्टर ({item.get('village_hi', item['village'])}, n={item.get('samples', 10)})",
                    "source": item["source"],
                    "tested_date": item.get("tested_date"),
                    "samples": item.get("samples", 10),
                    "texture": item.get("texture", "sandy-loam"),
                    "soil": Soil.model_validate(soil_dict).model_dump(mode="json"),
                }
    block_data = baselines["block_baselines"].get(block) or baselines["block_baselines"]["Roorkee"]
    soil_dict = {
        k: block_data[k] for k in SOIL_VALUE_KEYS if k in block_data and block_data[k] is not None
    }
    soil_dict.setdefault("basis", "elemental")
    return {
        "tier": "block_baseline",
        "tier_label_en": f"Published Block Soil Baseline — {block} (KVK Dhanauri / Pachauri et al. 2023, n={block_data['samples']})",
        "tier_label_hi": f"ब्लॉक मिट्टी औसत — {block_data['block_hi']} (KVK धनौरी / पचौरी आदि 2023, n={block_data['samples']})",
        "source": baselines["source"],
        "samples": block_data["samples"],
        "texture": block_data.get("texture", "sandy-loam"),
        "summary_en": block_data.get("summary_en", ""),
        "summary_hi": block_data.get("summary_hi", ""),
        "soil": Soil.model_validate(soil_dict).model_dump(mode="json"),
    }


def suggested_budget_rs(crop: str, area_ha: float) -> float:
    """Practical full-dose fertilizer budget estimate for the farmer's field size."""
    per_ha = {"wheat": 4600.0, "sugarcane": 6200.0, "rice": 4200.0, "maize": 4200.0}.get(
        crop, 4600.0
    )
    return float(max(300, round(per_ha * area_ha / 50) * 50))


def build_autofill(
    data_dir: Path,
    db=None,
    block: str | None = None,
    village: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    query: str | None = None,
    crop: str = "wheat",
    area_ha: float = 0.316,
    weather_enabled: bool = True,
) -> dict:
    """One-call automatic resolution of GPS, block, village, soil profile, live weather, and real-time irrigation."""
    blocks_data = load_blocks(data_dir)
    loc = resolve_location(
        blocks_data,
        block=block,
        village=village,
        lat=lat,
        lon=lon,
        query=query,
        online_geocode=weather_enabled,
    )
    soil_profile = resolve_soil_profile(loc["block"], loc["village"], data_dir, db=db)
    texture = soil_profile.get("texture") or loc.get("texture") or "sandy-loam"
    forecast = get_forecast(loc["latitude"], loc["longitude"], enabled=weather_enabled)
    today = date.today()
    water_preview = plan_irrigation(
        crop if crop in {"wheat", "sugarcane", "rice", "maize"} else "wheat",
        today,
        texture,
        max(0.05, min(100.0, area_ha)),
        data_dir,
        flow_lps=10.0,
        turn_hours=4.0,
        forecast=forecast,
    )
    return {
        "location": loc,
        "soil_profile": soil_profile,
        "texture": texture,
        "weather": forecast,
        "realtime_water": water_preview["realtime"],
        "defaults": {
            "sowing_date": today.isoformat(),
            "irrigation_method": water_preview["method"],
            "flow_lps": 10.0,
            "turn_hours": 4.0,
            "suggested_budget_rs": suggested_budget_rs(crop, area_ha),
        },
    }


def priced_products(inputs: AdvisoryInput, data_dir: Path) -> tuple[list[Product], list[Product]]:
    products, _ = load_catalog(data_dir)
    known = {p.id for p in products}
    unknown = (set(inputs.prices) | set(inputs.unavailable) | set(inputs.current_practice)) - known
    if unknown:
        raise ValueError(f"Unknown fertilizer product(s): {', '.join(sorted(unknown))}.")
    for product in products:
        if product.id in inputs.prices:
            product.price_rs = round(inputs.prices[product.id], 2)
    available = [p for p in products if p.id not in inputs.unavailable]
    if not available:
        raise ValueError("At least one fertilizer product must be available.")
    if not any(p.N for p in available):
        raise ValueError(
            "No available product supplies nitrogen. Mark urea or a complex fertilizer as available."
        )
    return products, available


def season_warning(crop: str, sowing: date) -> str | None:
    key = (sowing.month, sowing.day)
    for start, end, _label in SEASONS[crop]:
        if start <= key <= end:
            return None
    windows = "; ".join(f"{s[1]}/{s[0]}–{e[1]}/{e[0]} ({label})" for s, e, label in SEASONS[crop])
    return f"Sowing date is outside the usual window for {crop} in this region ({windows}). Stage dates, water needs and doses may not fit; consult KVK about late-sown varieties and doses."


def compare_practice(inputs: AdvisoryInput, products: list[Product], required: dict) -> dict | None:
    bags = {k: v for k, v in inputs.current_practice.items() if v > 0}
    if not bags:
        return None
    by_id = {p.id: p for p in products}
    rows, nutrients, cost = [], dict.fromkeys(NUTRIENTS, 0.0), 0.0
    for product_id, count in bags.items():
        product = by_id[product_id]
        supplied = {n: count * product.weight_kg * product.fraction(n) for n in NUTRIENTS}
        for n in NUTRIENTS:
            nutrients[n] += supplied[n]
        cost += count * product.price_rs
        rows.append(
            {
                "id": product_id,
                "product": product.name,
                "product_hi": product.name_hi,
                "bags": count,
                "cost": round(count * product.price_rs, 2),
                "nutrients": supplied,
            }
        )
    return {
        "rows": rows,
        "nutrients": nutrients,
        "cost": round(cost, 2),
        "difference": {n: nutrients[n] - required[n] for n in NUTRIENTS},
    }


def build_advisory(inputs: AdvisoryInput, data_dir: Path, weather_enabled: bool = False) -> dict:
    required, method, warnings, breakdown = nutrient_requirement(
        inputs, load_profiles(data_dir), data_dir
    )
    products, available = priced_products(inputs, data_dir)
    _, price_source = load_catalog(data_dir)
    plan = optimize(required, inputs.budget, available)
    for row in plan["shopping"]:
        product = next(p for p in available if p.name == row["product"])
        row.update(id=product.id, product_hi=product.name_hi, price_rs=product.price_rs)
    location_note = None
    lat, lon = inputs.latitude, inputs.longitude
    if lat is None:
        block = load_blocks(data_dir)["blocks"][inputs.block]
        lat, lon = block["lat"], block["lon"]
        location_note = f"Weather uses the {block.get('fallback_of', inputs.block)} reference point; enter field coordinates for precision."
    forecast = get_forecast(lat, lon, weather_enabled)
    warnings.append(
        price_source if not inputs.prices else "Prices include your dealer prices where entered."
    )
    if plan["minimum_coverage"] < 0.999:
        warnings.append(
            "Budget-limited nutrient shortfalls remain. Coverage is not expected yield."
        )
    if not inputs.irrigation_at:
        warnings.append("Official canal schedules are pending; no water turn has been assumed.")
    if forecast["status"] != "live":
        warnings.append(forecast["reason"])
    elif location_note:
        warnings.append(location_note)
    if note := season_warning(inputs.crop, inputs.sowing_date):
        warnings.append(note)
    soil_report = interpret_soil(inputs.soil, data_dir, inputs.area_ha) if inputs.soil else None
    soil_origin = None
    if inputs.soil is not None:
        if inputs.soil_source in {"official_village", "block_baseline"}:
            profile_meta = resolve_soil_profile(inputs.block, inputs.village, data_dir)
            soil_origin = {
                "source_type": inputs.soil_source,
                "label_en": profile_meta["tier_label_en"],
                "label_hi": profile_meta["tier_label_hi"],
                "citation": profile_meta["source"],
            }
            warnings.append(
                f"Soil values auto-filled from: {profile_meta['tier_label_en']}. "
                "Individual fields can vary; get a free field-specific Soil Health Card when possible."
            )
        else:
            soil_origin = {
                "source_type": "card",
                "label_en": "Farmer's Soil Health Card (field-specific lab values)",
                "label_hi": "किसान का मृदा स्वास्थ्य कार्ड (खेत की अपनी जाँच)",
                "citation": "User-entered Soil Health Card",
            }
    water = plan_irrigation(
        inputs.crop,
        inputs.sowing_date,
        inputs.texture,
        inputs.area_ha,
        data_dir,
        inputs.irrigation_method,
        inputs.flow_lps,
        inputs.turn_hours,
        inputs.max_irrigations,
        forecast,
    )
    practice = compare_practice(inputs, products, required)
    schedule = application_schedule(inputs, plan["shopping"], forecast)
    hindi_names = {p.name: p.name_hi for p in products}
    for stage in schedule:
        stage["allocations_hi"] = {
            hindi_names.get(k, k): v for k, v in stage["allocations"].items()
        }
    by_id = {p.id: p for p in products}
    report = {
        "inputs": inputs.model_dump(mode="json"),
        "area_ha": inputs.area_ha,
        "method": method,
        "warnings": warnings,
        "breakdown": breakdown,
        "plan": plan,
        "weather": forecast,
        "schedule": schedule,
        "soil_report": soil_report,
        "soil_origin": soil_origin,
        "water": water,
        "practice": practice,
        "prices": {
            p.id: {
                "name": p.name,
                "name_hi": p.name_hi,
                "price_rs": p.price_rs,
                "weight_kg": p.weight_kg,
                "available": p.id not in inputs.unavailable,
            }
            for p in products
        },
        "cost_difference": (
            round(practice["cost"] - plan["total_cost"], 2)
            if practice
            else round(inputs.baseline_cost - plan["total_cost"], 2)
            if inputs.baseline_cost is not None
            else None
        ),
    }
    report["recommendations"] = build_recommendations(
        inputs, breakdown, soil_report, plan, practice, water, by_id
    )
    return report
