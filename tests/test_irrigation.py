from datetime import date

import pytest

from app import ROOT
from engine.irrigation import UK_BIGHA_M2, effective_rain_month, plan_irrigation

DATA = ROOT / "data"
WHEAT = date(2026, 11, 10)


def plan(crop="wheat", sowing=WHEAT, texture="loam", area=1.0, **kwargs):
    return plan_irrigation(crop, sowing, texture, area, DATA, **kwargs)


def test_wheat_schedule_is_agronomically_plausible():
    result = plan(method_id="border")
    days = [e["das"] for e in result["events"]]
    assert 4 <= len(days) <= 7  # IIWBR: 5–6 irrigations for timely-sown wheat
    assert 18 <= days[0] <= 25  # crown root initiation is never skipped
    assert all(4.9 <= e["gross_cm"] <= 9 for e in result["events"])
    assert result["season"]["stress_days"] <= 7


@pytest.mark.parametrize(
    "crop,sowing",
    [
        ("wheat", WHEAT),
        ("maize", date(2027, 2, 20)),
        ("sugarcane", date(2027, 2, 25)),
        ("rice", date(2027, 7, 1)),
    ],
)
def test_volumes_are_consistent_with_depth_and_area(crop, sowing):
    result = plan(crop, sowing, area=0.25, flow_lps=10)
    for event in result["events"]:
        assert event["volume_m3"] == pytest.approx(event["gross_mm"] * 0.25 * 10, abs=0.06)
        assert event["litres_per_bigha"] == pytest.approx(event["gross_mm"] * UK_BIGHA_M2, abs=1)
        assert event["pump_hours"] == pytest.approx(event["volume_m3"] / 36, abs=0.01)
        assert event["gross_mm"] >= event["net_mm"]
    total = sum(e["volume_m3"] for e in result["events"])
    assert result["season"]["volume_m3"] == pytest.approx(
        total, abs=0.1 * max(1, len(result["events"]))
    )


def test_efficient_methods_use_less_water_and_comparison_is_sorted():
    result = plan(texture="sandy-loam", method_id="wild_flood")
    volumes = {c["id"]: c["season_m3"] for c in result["comparison"]}
    assert volumes["sprinkler"] < volumes["border"] < volumes["wild_flood"]
    assert [c["season_m3"] for c in result["comparison"]] == sorted(volumes.values())
    assert next(c for c in result["comparison"] if c["id"] == "wild_flood")["saving_pct"] == 0
    assert all(c["pros_hi"] and c["cons_en"] for c in result["comparison"])


def test_sandy_soil_needs_more_frequent_lighter_irrigations():
    sandy, loam = plan(texture="sandy"), plan(texture="loam")
    assert sandy["season"]["count"] > loam["season"]["count"]
    assert max(e["net_mm"] for e in sandy["events"]) < max(e["net_mm"] for e in loam["events"])


def test_awd_never_uses_more_water_than_continuous_flooding():
    for texture in ("sandy-loam", "loam", "clay"):
        result = plan("rice", date(2027, 7, 1), texture, method_id="rice_awd")
        volumes = {c["id"]: c["season_m3"] for c in result["comparison"]}
        assert volumes["rice_awd"] <= volumes["rice_cf"]
        assert result["events"][0]["stage_en"].startswith("Puddling")


def test_limited_water_prioritises_critical_wheat_stages():
    result = plan(texture="sandy", max_irrigations=2)
    assert result["limited"]
    assert [e["das"] for e in result["events"]] == [21, 87]
    assert "Only 2" in result["notes_en"][0]


def test_turn_coverage_and_method_validation():
    result = plan(area=1, flow_lps=10, turn_hours=2, method_id="border")
    assert result["turn"]["delivered_m3"] == 72
    assert 0 < result["turn"]["coverage"] < 1
    with pytest.raises(ValueError, match="does not suit"):
        plan(method_id="rice_awd")


def test_dependable_rain_formula():
    assert effective_rain_month(0) == 0
    assert effective_rain_month(10) == 0
    assert effective_rain_month(50) == pytest.approx(20)
    assert effective_rain_month(100) == pytest.approx(56)


def test_forecast_rain_marks_postponement():
    first_day = plan()["events"][0]["date"]
    forecast = {"status": "live", "days": [{"date": first_day, "rain_mm": 30}]}
    result = plan_irrigation("wheat", WHEAT, "loam", 1, DATA, forecast=forecast)
    flagged = [e for e in result["events"] if e.get("postpone")]
    assert flagged and flagged[0]["date"] == first_day
    dry = {"status": "live", "days": [{"date": first_day, "rain_mm": 0}]}
    first = plan_irrigation("wheat", WHEAT, "loam", 1, DATA, forecast=dry)["events"][0]
    assert first["postpone"] is False and first["forecast_rain_mm"] == 0


@pytest.mark.parametrize("texture", ["sandy", "sandy-loam", "loam", "clay-loam", "clay"])
@pytest.mark.parametrize("sowing", [date(2026, 11, 1), date(2026, 11, 20), date(2026, 12, 15)])
def test_wheat_never_irrigates_back_to_back(texture, sowing):
    days = [e["das"] for e in plan(sowing=sowing, texture=texture)["events"]]
    assert all(b - a >= 3 for a, b in zip(days, days[1:], strict=False))
    assert any(15 <= d <= 25 for d in days)  # CRI is always covered


def test_awd_saving_is_in_published_range():
    result = plan("rice", date(2027, 7, 1), "loam", method_id="rice_awd")
    saving = next(c for c in result["comparison"] if c["id"] == "rice_awd")["saving_pct"]
    assert 10 <= saving <= 35
