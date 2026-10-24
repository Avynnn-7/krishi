import pytest

from app import ROOT
from engine.models import Soil
from engine.soil_card import gauge, interpret_soil

DATA = ROOT / "data"


def ratings(**values):
    return {i["key"]: i["rating"] for i in interpret_soil(Soil(**values), DATA)["items"]}


@pytest.mark.parametrize(
    "n,expected", [(279.9, "low"), (280, "medium"), (560, "medium"), (560.1, "high")]
)
def test_nitrogen_boundaries(n, expected):
    assert ratings(N=n, P=15, K=200)["N"] == expected


def test_oxide_basis_is_converted_before_rating():
    # 30 kg/ha P2O5 = 13.1 kg/ha P (medium); as elemental 30 would be high.
    assert ratings(N=300, P=30, K=200, basis="oxide")["P"] == "medium"
    assert ratings(N=300, P=30, K=200)["P"] == "high"
    assert ratings(N=300, P=15, K=120, basis="oxide")["K"] == "low"


def test_micronutrient_deficiencies_produce_field_quantities():
    report = interpret_soil(
        Soil(N=300, P=15, K=200, zinc=0.4, sulphur=8, boron=0.3, iron=2), DATA, 0.5
    )
    amendments = {a["nutrient"]: a for a in report["amendments"]}
    assert amendments["zinc"]["kg_field"] == 12.5
    assert amendments["sulphur"]["kg_field"] == 100
    assert amendments["boron"]["kg_field"] == 5
    assert "iron" not in amendments  # foliar advice only, no invented soil quantity
    assert report["attention_count"] == 4


def test_ph_ec_classes_and_sodic_gypsum():
    report = interpret_soil(Soil(N=300, P=15, K=200, ph=8.8, ec=5, organic_carbon=0.3), DATA)
    found = {i["key"]: i["rating"] for i in report["items"]}
    assert found == {
        "N": "medium",
        "P": "medium",
        "K": "medium",
        "organic_carbon": "low",
        "ph": "sodic",
        "ec": "very_saline",
    }
    assert any(a["nutrient"] == "ph" and a["kg_ha"] is None for a in report["amendments"])
    assert all(i["meaning_hi"] for i in report["items"])


def test_unit_mistakes_are_flagged():
    report = interpret_soil(Soil(N=1500, P=200, K=2000), DATA)
    assert len(report["plausibility"]) == 3


def test_gauge_scale_is_bounded_and_monotonic():
    values = [gauge(v, 280, 560) for v in (0, 140, 280, 420, 560, 900, 5000)]
    assert values == sorted(values)
    assert values[0] == 0 and values[-1] == 1
    assert values[2] == pytest.approx(1 / 3) and values[4] == pytest.approx(2 / 3)
