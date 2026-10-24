import pytest

from app import ROOT
from engine.models import AdvisoryInput, Soil
from engine.service import build_advisory
from engine.stcr import nutrient_requirement

DATA = ROOT / "data"


def test_soil_ratings_scale_reference_dose(inputs):
    soil = Soil(N=200, P=30, K=200)  # low N, high P, medium K
    required, method, _, breakdown = nutrient_requirement(
        inputs.model_copy(update={"soil": soil}), {}, DATA
    )
    assert required == pytest.approx({"N": 187.5, "P2O5": 45, "K2O": 40})
    assert breakdown["kind"] == "rating" and "not STCR" in method


def test_fym_credit_is_deducted_and_never_negative(inputs):
    required = nutrient_requirement(inputs.model_copy(update={"fym_t_ha": 10}), {}, DATA)[0]
    assert required == pytest.approx({"N": 135, "P2O5": 47.5, "K2O": 5})
    required = nutrient_requirement(inputs.model_copy(update={"fym_t_ha": 40}), {}, DATA)[0]
    assert required["K2O"] == 0


def test_price_overrides_and_unavailable_products(inputs):
    custom = inputs.model_copy(
        update={"prices": {"urea": 300}, "unavailable": ["dap"], "budget": 20000}
    )
    report = build_advisory(custom, DATA)
    rows = {r["id"]: r for r in report["plan"]["shopping"]}
    assert "dap" not in rows
    assert rows["urea"]["price_rs"] == 300
    assert rows["urea"]["cost"] == rows["urea"]["bags"] * 300
    assert report["prices"]["dap"]["available"] is False


@pytest.mark.parametrize(
    "update,match",
    [
        (
            {"unavailable": ["urea", "dap", "mop", "ssp", "npk_12_32_16", "npk_10_26_26"]},
            "At least one",
        ),
        ({"unavailable": ["urea", "dap", "npk_12_32_16", "npk_10_26_26"]}, "nitrogen"),
        ({"prices": {"gold": 10}}, "Unknown fertilizer"),
    ],
)
def test_invalid_catalog_changes_are_rejected(inputs, update, match):
    with pytest.raises(ValueError, match=match):
        build_advisory(inputs.model_copy(update=update), DATA)


def test_current_practice_comparison_flags_dap_habit(inputs):
    habit = inputs.model_copy(
        update={
            "soil": Soil(N=200, P=30, K=200),
            "current_practice": {"urea": 4, "dap": 4},
            "budget": 10000,
        }
    )
    report = build_advisory(habit, DATA)
    practice = report["practice"]
    assert practice["nutrients"]["P2O5"] == pytest.approx(92)
    assert practice["difference"]["P2O5"] == pytest.approx(92 - 45)
    assert practice["cost"] == pytest.approx(4 * 266.5 + 4 * 1350)
    titles = [r["title_en"] for r in report["recommendations"]]
    assert titles[0].startswith(
        ("Phosphorus is high", "Nitrogen is low", "Your usual practice over-applies")
    )
    assert any("over-applies P2O5" in t for t in titles)
    assert all(r["title_hi"] and r["detail_hi"] for r in report["recommendations"])


def test_no_soil_card_recommends_testing_and_block_weather_point(inputs):
    report = build_advisory(inputs, DATA)
    assert report["recommendations"][0]["title_en"].startswith("Get your soil tested")
    assert report["soil_report"] is None
    assert report["water"]["events"]


def test_wild_flooding_recommends_cheapest_better_method(inputs):
    report = build_advisory(inputs.model_copy(update={"irrigation_method": "wild_flood"}), DATA)
    water = [r for r in report["recommendations"] if r["category"] == "water"]
    assert water[0]["title_en"].startswith("Switch to Check basins")


def test_out_of_season_sowing_is_warned(inputs):
    report = build_advisory(
        inputs.model_copy(update={"sowing_date": inputs.sowing_date.replace(month=5, day=1)}), DATA
    )
    assert any("outside the usual window" in w for w in report["warnings"])


def test_large_bigha_field_is_accepted():
    model = AdvisoryInput(
        block="Laksar",
        village="X",
        crop="sugarcane",
        sowing_date="2027-03-01",
        area=150,
        area_unit="bigha",
        bigha_m2=632.29,
        budget=50000,
    )
    assert model.area_ha == pytest.approx(9.484, abs=0.001)
