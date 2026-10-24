import logging
import math
import re
import threading
import time
from datetime import date, datetime, timezone

import requests

logger = logging.getLogger(__name__)
CACHE_SECONDS = 1800
_cache: dict[tuple[float, float], tuple[float, dict]] = {}
_lock = threading.Lock()


def _valid_num(val: object, allow_negative: bool = False) -> bool:
    if isinstance(val, bool) or not isinstance(val, (float, int)) or not math.isfinite(val):
        return False
    return True if allow_negative else val >= 0


def get_forecast(latitude: float | None, longitude: float | None, enabled: bool = False) -> dict:
    if not enabled:
        return {
            "status": "unavailable",
            "reason": "Live weather is disabled. Check a current local forecast.",
            "days": [],
        }
    if latitude is None or longitude is None:
        return {
            "status": "unavailable",
            "reason": "No coordinates supplied; weather cannot be checked.",
            "days": [],
        }
    key = (round(latitude, 2), round(longitude, 2))
    with _lock:
        cached = _cache.get(key)
        if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
            return cached[1]
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "daily": (
                    "precipitation_sum,et0_fao_evapotranspiration,"
                    "temperature_2m_max,temperature_2m_min,precipitation_probability_max"
                ),
                "timezone": "Asia/Kolkata",
                "forecast_days": 7,
            },
            timeout=(3, 8),
        )
        response.raise_for_status()
        payload = response.json()
        daily = payload["daily"]
        dates, rain = daily["time"], daily["precipitation_sum"]
        if len(dates) != len(rain) or not dates:
            raise ValueError("Incomplete daily weather data.")
        et0_list = daily.get("et0_fao_evapotranspiration")
        tmax_list = daily.get("temperature_2m_max")
        tmin_list = daily.get("temperature_2m_min")
        prob_list = daily.get("precipitation_probability_max")
        days = []
        for idx, (day, mm) in enumerate(zip(dates, rain, strict=True)):
            date.fromisoformat(day)
            if not _valid_num(mm):
                raise ValueError("Missing or invalid rain amount.")
            entry: dict[str, float | str] = {"date": day, "rain_mm": mm}
            if isinstance(et0_list, list) and idx < len(et0_list) and _valid_num(et0_list[idx]):
                entry["et0_mm"] = round(float(et0_list[idx]), 2)
            if (
                isinstance(tmax_list, list)
                and idx < len(tmax_list)
                and _valid_num(tmax_list[idx], allow_negative=True)
            ):
                entry["temp_max_c"] = round(float(tmax_list[idx]), 1)
            if (
                isinstance(tmin_list, list)
                and idx < len(tmin_list)
                and _valid_num(tmin_list[idx], allow_negative=True)
            ):
                entry["temp_min_c"] = round(float(tmin_list[idx]), 1)
            if isinstance(prob_list, list) and idx < len(prob_list) and _valid_num(prob_list[idx]):
                entry["rain_prob_pct"] = round(float(prob_list[idx]))
            days.append(entry)
        if len({day["date"] for day in days}) != len(days):
            raise ValueError("Duplicate forecast dates.")
        rain_7d = round(sum(float(d["rain_mm"]) for d in days), 1)
        rain_48h = round(sum(float(d["rain_mm"]) for d in days[:2]), 1)
        et0_vals = [float(d["et0_mm"]) for d in days if "et0_mm" in d]
        et0_7d = round(sum(et0_vals), 1) if et0_vals else None
        mean_et0 = round(et0_7d / len(et0_vals), 2) if et0_vals and et0_7d is not None else None
        result = {
            "status": "live",
            "source": "Open-Meteo",
            "days": days,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "point": [key[0], key[1]],
            "summary": {
                "rain_48h_mm": rain_48h,
                "rain_7d_mm": rain_7d,
                "et0_7d_mm": et0_7d,
                "mean_et0_mm_day": mean_et0,
                "today_temp_max_c": days[0].get("temp_max_c"),
                "today_temp_min_c": days[0].get("temp_min_c"),
                "today_rain_prob_pct": days[0].get("rain_prob_pct"),
            },
        }
        with _lock:
            _cache[key] = (time.monotonic(), result)
        return result
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        logger.warning("Weather provider unavailable: %s", type(exc).__name__)
        return {
            "status": "unavailable",
            "reason": "Weather service failed; rain risk is unknown. Check locally.",
            "days": [],
        }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def parse_coordinates_or_maps_url(query: str) -> tuple[float, float] | None:
    """Extract (lat, lon) from raw coordinates or a Google Maps / geo URL."""
    patterns = [
        r"@(-?\d{1,2}\.\d+),\s*(-?\d{1,3}\.\d+)",
        r"[?&](?:q|ll|query)=(-?\d{1,2}\.\d+),\s*(-?\d{1,3}\.\d+)",
        r"^\s*(-?\d{1,2}\.\d+)\s*[,\s]\s*(-?\d{1,3}\.\d+)\s*$",
    ]
    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            lat, lon = float(match.group(1)), float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return round(lat, 5), round(lon, 5)
    return None


def resolve_location(
    blocks_data: dict,
    block: str | None = None,
    village: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    query: str | None = None,
    online_geocode: bool = True,
) -> dict:
    """Resolve block, village, and GPS coordinates from GPS, village name, or search query."""
    blocks = blocks_data["blocks"]
    if query and (coords := parse_coordinates_or_maps_url(query)):
        lat, lon = coords

    # 1. If lat/lon provided (from GPS or Google Maps link), find nearest Haridwar village & block
    if lat is not None and lon is not None:
        best_village = None
        best_dist = 1e9
        best_block = block or "Roorkee"
        for b_name, b_info in blocks.items():
            for v in b_info.get("villages", []):
                dist = haversine_km(lat, lon, v["lat"], v["lon"])
                if dist < best_dist:
                    best_dist = dist
                    best_village = v
                    best_block = b_name
            b_dist = haversine_km(lat, lon, b_info["lat"], b_info["lon"])
            if b_dist < best_dist:
                best_dist = b_dist
                best_block = b_name
        resolved_block = block if block in blocks else best_block
        resolved_village = village
        texture = blocks[resolved_block].get("default_texture", "sandy-loam")
        if best_village and best_dist <= 15.0:
            if not resolved_village:
                resolved_village = best_village["name"]
            texture = best_village.get("texture", texture)
        return {
            "block": resolved_block,
            "block_hi": blocks[resolved_block]["hi"],
            "village": resolved_village or best_block,
            "village_hi": best_village["hi"]
            if best_village and best_dist <= 15.0
            else blocks[resolved_block]["hi"],
            "latitude": round(lat, 5),
            "longitude": round(lon, 5),
            "texture": texture,
            "distance_km": round(best_dist, 2),
            "source": "gps_coordinates",
        }

    # 2. Match village name or search query against local Haridwar–Roorkee gazetteer
    search_term = (query or village or "").strip().lower()
    if search_term:
        for b_name, b_info in blocks.items():
            if block and b_name != block:
                continue
            for v in b_info.get("villages", []):
                if (
                    search_term in {v["name"].lower(), v["hi"].lower()}
                    or search_term in v["name"].lower()
                ):
                    return {
                        "block": b_name,
                        "block_hi": b_info["hi"],
                        "village": v["name"],
                        "village_hi": v["hi"],
                        "latitude": v["lat"],
                        "longitude": v["lon"],
                        "texture": v.get("texture", b_info.get("default_texture", "sandy-loam")),
                        "source": "haridwar_gazetteer",
                    }
        # Also search across all blocks if not found in selected block
        for b_name, b_info in blocks.items():
            for v in b_info.get("villages", []):
                if (
                    search_term in {v["name"].lower(), v["hi"].lower()}
                    or search_term in v["name"].lower()
                ):
                    return {
                        "block": b_name,
                        "block_hi": b_info["hi"],
                        "village": v["name"],
                        "village_hi": v["hi"],
                        "latitude": v["lat"],
                        "longitude": v["lon"],
                        "texture": v.get("texture", b_info.get("default_texture", "sandy-loam")),
                        "source": "haridwar_gazetteer",
                    }

    # 3. Optional live geocoding via Open-Meteo Geocoding API for any unlisted village
    if online_geocode and search_term and len(search_term) >= 2:
        try:
            resp = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": query or village, "count": 5, "country": "IN", "language": "en"},
                timeout=(2, 4),
            )
            resp.raise_for_status()
            for item in resp.json().get("results", []):
                if item.get("admin1") in {"Uttarakhand", "Uttar Pradesh"}:
                    return resolve_location(
                        blocks_data,
                        block=block,
                        village=item.get("name") or village,
                        lat=float(item["latitude"]),
                        lon=float(item["longitude"]),
                        online_geocode=False,
                    )
        except (requests.RequestException, ValueError, KeyError, TypeError):
            pass

    # 4. Fallback to block town centre
    chosen_block = block if block in blocks else "Roorkee"
    b_info = blocks[chosen_block]
    v_default = b_info["villages"][0] if b_info.get("villages") else None
    return {
        "block": chosen_block,
        "block_hi": b_info["hi"],
        "village": village or (v_default["name"] if v_default else chosen_block),
        "village_hi": v_default["hi"] if v_default and not village else (village or b_info["hi"]),
        "latitude": b_info["lat"],
        "longitude": b_info["lon"],
        "texture": b_info.get("default_texture", "sandy-loam"),
        "source": "block_reference",
    }
