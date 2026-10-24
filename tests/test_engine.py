import itertools
import math
from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from app import ROOT
from engine.models import NUTRIENTS, AdvisoryInput, Product, Soil
from engine.optimizer import optimize
from engine.service import build_advisory
from engine.simulator import Scenario, compare_scenarios
from engine.stcr import Coefficient, Profile, calculate_stcr, nutrient_requirement
from engine.timing import IST, application_schedule, rain_risk


def test_stcr_percent_normalization_and_clamp():
    coeffs = {n: Coefficient(nr_per_quintal=2, cs_percent=20, cf_percent=50) for n in NUTRIENTS}
    result = calculate_stcr(50, {"N": 100, "P2O5": 1000, "K2O": 0}, coeffs)
    assert result == {"N": 160, "P2O5": 0, "K2O": 200}
    with pytest.raises(ValidationError):
        Coefficient(nr_per_quintal=2, cs_percent=20, cf_percent=0)
    with pytest.raises(ValueError):
        calculate_stcr(math.nan, {"N": 1, "P2O5": 1, "K2O": 1}, coeffs)


def test_profile_units_and_crop_bounds(inputs):
    coefficients = {
        n: Coefficient(nr_per_quintal=2, cs_percent=20, cf_percent=50) for n in NUTRIENTS
    }
    profile = Profile(
        id="test",
        crop="wheat",
        region="test soil",
        source="Synthetic test fixture",
        verified_by="Test only",
        soil_basis="elemental",
        min_yield=20,
        max_yield=80,
        coefficients=coefficients,
    )
    updated = inputs.model_copy(update={"soil": Soil(N=100, P=20, K=100), "stcr_profile": "test"})
    a = nutrient_requirement(updated, {"test": profile})[0]
    updated.soil = Soil(N=100, P=20 * 2.2914, K=100 * 1.2046, basis="oxide")
    b = nutrient_requirement(updated, {"test": profile})[0]
    assert a == pytest.approx(b)
    updated.target_yield = 100
    with pytest.raises(ValueError, match="outside"):
        nutrient_requirement(updated, {"test": profile})


def test_reference_does_not_invent_soil_or_use_target(inputs):
    a, method, warnings, _ = nutrient_requirement(inputs, {})
    b = nutrient_requirement(inputs.model_copy(update={"target_yield": 100}), {})[0]
    assert a == b
    assert "not STCR" in method
    assert any("No soil values were invented" in w for w in warnings)
    assert a == {"N": 150, "P2O5": 60, "K2O": 40}


def test_field_area_and_units(inputs):
    raw = inputs.model_dump()
    raw.update(area=1, area_unit="acre")
    assert AdvisoryInput.model_validate(raw).area_ha == pytest.approx(0.40468564224)
    raw.update(area=2, area_unit="bigha", bigha_m2=1000)
    assert AdvisoryInput.model_validate(raw).area_ha == pytest.approx(0.2)
    raw["bigha_m2"] = None
    with pytest.raises(ValidationError):
        AdvisoryInput.model_validate(raw)


@pytest.mark.parametrize(
    "field,value",
    [
        ("budget", -1),
        ("area", 0),
        ("budget", math.nan),
        ("area", math.inf),
        ("budget", 2000.001),
        ("latitude", 300),
        ("village", ""),
        ("block", "unknown"),
        ("irrigation_cycle_days", 0),
    ],
)
def test_invalid_inputs_rejected(inputs, field, value):
    raw = inputs.model_dump()
    raw[field] = value
    with pytest.raises(ValidationError):
        AdvisoryInput.model_validate(raw)


@pytest.mark.parametrize("budget", [0, 100, 266.5, 2000, 5000, 100000])
def test_optimizer_budget_application_and_bag_invariants(products, budget):
    required = {"N": 150, "P2O5": 60, "K2O": 40}
    plan = optimize(required, budget, products)
    assert plan["total_cost"] <= budget
    assert all(isinstance(r["bags"], int) and r["bags"] >= 0 for r in plan["shopping"])
    for n in NUTRIENTS:
        assert plan["delivered"][n] <= required[n] + 1e-4
    for row in plan["shopping"]:
        assert row["apply_kg"] <= row["purchased_kg"] + 1e-4
        assert row["leftover_kg"] + row["apply_kg"] == pytest.approx(row["purchased_kg"])
    if budget == 100000:
        assert plan["minimum_coverage"] == pytest.approx(1, abs=1e-6)
        assert plan["total_cost"] < 10000


def test_zero_need_and_zero_phosphorus(products):
    plan = optimize(dict.fromkeys(NUTRIENTS, 0), 2000, products)
    assert plan["total_cost"] == 0
    assert plan["minimum_coverage"] == 1
    plan = optimize({"N": 50, "P2O5": 0, "K2O": 0}, 5000, products)
    assert next(row for row in plan["shopping"] if row["product"] == "DAP")["bags"] == 0
    assert plan["total_cost"] == 799.5


@pytest.mark.parametrize("budget", [0, 4, 7, 12, 20, 40])
def test_optimizer_matches_exhaustive_lexicographic_oracle(budget):
    products = [
        Product(name="N", weight_kg=10, price_rs=4, N=1, P2O5=0, K2O=0),
        Product(name="P", weight_kg=10, price_rs=5, N=0, P2O5=1, K2O=0),
        Product(name="K", weight_kg=10, price_rs=7, N=0, P2O5=0, K2O=1),
    ]
    required = {"N": 15, "P2O5": 10, "K2O": 20}
    candidates = []
    for bags in itertools.product(range(5), repeat=3):
        cost = sum(count * p.price_rs for count, p in zip(bags, products, strict=True))
        if cost <= budget:
            ratios = [min(1, bags[i] * 10 / required[n]) for i, n in enumerate(NUTRIENTS)]
            candidates.append((min(ratios), sum(ratios), -cost))
    best = max(candidates)
    plan = optimize(required, budget, products)
    assert plan["minimum_coverage"] == pytest.approx(best[0], abs=1e-6)
    assert sum(plan["coverage"].values()) == pytest.approx(best[1], abs=1e-6)
    assert plan["total_cost"] == -best[2]


def test_schedule_conserves_products_and_compound_n(inputs, products):
    plan = optimize({"N": 150, "P2O5": 60, "K2O": 40}, 10000, products)
    weather = {"status": "unavailable", "days": []}
    schedule = application_schedule(inputs, plan["shopping"], weather)
    for row in plan["shopping"]:
        total = sum(stage["allocations"].get(row["product"], 0) for stage in schedule)
        assert total == pytest.approx(row["apply_kg"], abs=1e-5)
    assert all(stage["risk"] == "unknown" for stage in schedule)
    fractions = {p.name: p.N for p in products}
    basal_n = sum(kg * fractions[name] for name, kg in schedule[0]["allocations"].items())
    assert basal_n == pytest.approx(plan["delivered"]["N"] / 3, abs=1e-4)
    assert all("DAP" not in stage["allocations"] for stage in schedule[1:])


def test_risk_threshold_and_incomplete_horizon():
    start = datetime(2026, 10, 20, 8, tzinfo=IST)
    days = [{"date": f"2026-10-{d}", "rain_mm": 0} for d in (19, 20, 21)]
    days[1]["rain_mm"] = 20
    assert rain_risk(start, start, {"status": "live", "days": days})[0] == "lower"
    days[1]["rain_mm"] = 20.01
    assert rain_risk(start, start, {"status": "live", "days": days})[0] == "high"
    days[1]["rain_mm"] = 0
    assert rain_risk(start, start, {"status": "live", "days": days[:2]})[0] == "unknown"


def test_canal_turn_sync_never_moves_application_before_stage(inputs, products):
    turn = datetime.combine(inputs.sowing_date, datetime.min.time(), IST) + timedelta(hours=8)
    inputs = inputs.model_copy(update={"irrigation_at": turn, "texture": "sandy"})
    plan = optimize({"N": 150, "P2O5": 60, "K2O": 40}, 2000, products)
    schedule = application_schedule(inputs, plan["shopping"], {"status": "unavailable", "days": []})
    first = schedule[1]
    arrival = datetime.fromisoformat(first["irrigation"])
    assert arrival - datetime.fromisoformat(first["start"]) == timedelta(hours=12)
    assert arrival - datetime.fromisoformat(first["end"]) == timedelta(hours=6)
    assert first["start"][:10] >= first["stage_date"]


def test_pipeline_does_not_claim_unentered_savings(inputs):
    result = build_advisory(inputs, ROOT / "data")
    assert result["cost_difference"] is None
    assert result["inputs"]["soil"] is None
    assert result["weather"]["status"] == "unavailable"


def test_simulator_accounts_for_tradeoffs_and_zero_price():
    result = compare_scenarios(Scenario())
    assert result["fertilizer_saving"] == 0
    assert result["difference"] == 4000
    assert result["intercrop_profit"] == 94000
    assert compare_scenarios(Scenario(intercrop_price=0))["break_even_yield"] is None
    assert compare_scenarios(Scenario(main_revenue_loss_pct=50))["difference"] < 0
