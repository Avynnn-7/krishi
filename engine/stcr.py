import json
from pathlib import Path

from pydantic import Field, model_validator

from engine.models import NUTRIENTS, AdvisoryInput, Crop, StrictModel, valid_nutrients

# Reference doses are not calibrated STCR equations or individual field prescriptions.
REFERENCE_DOSES = {
    "wheat": {"N": 150.0, "P2O5": 60.0, "K2O": 40.0},
    "sugarcane": {"N": 150.0, "P2O5": 60.0, "K2O": 60.0},
    "rice": {"N": 120.0, "P2O5": 60.0, "K2O": 40.0},
    "maize": {"N": 120.0, "P2O5": 60.0, "K2O": 40.0},
}


class Coefficient(StrictModel):
    nr_per_quintal: float = Field(gt=0, le=100)
    cs_percent: float = Field(ge=0, le=100)
    cf_percent: float = Field(gt=0, le=100)


class Profile(StrictModel):
    id: str
    crop: Crop
    region: str
    source: str = Field(min_length=5)
    verified_by: str = Field(min_length=3)
    soil_basis: str = Field(pattern="^(elemental|oxide)$")
    min_yield: float = Field(gt=0)
    max_yield: float = Field(gt=0)
    coefficients: dict[str, Coefficient]

    @model_validator(mode="after")
    def validate_profile(self) -> "Profile":
        if set(self.coefficients) != set(NUTRIENTS) or self.max_yield < self.min_yield:
            raise ValueError("Profile must cover all nutrients and a valid yield range.")
        return self


def load_profiles(data_dir: Path) -> dict[str, Profile]:
    raw = json.loads((data_dir / "stcr_coefficients.json").read_text())
    profiles = [Profile.model_validate(item) for item in raw["profiles"]]
    if len({p.id for p in profiles}) != len(profiles):
        raise ValueError("Duplicate STCR profile IDs.")
    return {p.id: p for p in profiles}


def calculate_stcr(
    target_yield: float, soil_values: dict[str, float], coefficients: dict[str, Coefficient]
) -> dict[str, float]:
    import math

    valid_nutrients(soil_values)
    if not math.isfinite(target_yield) or target_yield <= 0:
        raise ValueError("Target yield must be positive and finite.")
    if set(coefficients) != set(NUTRIENTS):
        raise ValueError("All three nutrient coefficients are required.")
    return {
        nutrient: max(
            0.0,
            coeff.nr_per_quintal * target_yield / (coeff.cf_percent / 100)
            - coeff.cs_percent * soil_values[nutrient] / coeff.cf_percent,
        )
        for nutrient, coeff in coefficients.items()
    }


def nutrient_requirement(
    inputs: AdvisoryInput, profiles: dict[str, Profile], data_dir: Path | None = None
) -> tuple[dict[str, float], str, list[str], dict]:
    from engine.soil_card import interpret_soil, load_ratings

    warnings = ["Research prototype: have a qualified agronomist review before field use."]
    ratings = None
    if inputs.soil is not None and data_dir is not None:
        ratings = interpret_soil(inputs.soil, data_dir)["nutrient_ratings"]
    factors = dict.fromkeys(NUTRIENTS, 1.0)
    base = REFERENCE_DOSES[inputs.crop]
    if inputs.stcr_profile:
        if inputs.stcr_profile not in profiles:
            raise ValueError("Requested STCR profile is not available.")
        profile = profiles[inputs.stcr_profile]
        if (
            profile.crop != inputs.crop
            or not profile.min_yield <= inputs.target_yield <= profile.max_yield
        ):
            raise ValueError("Crop or target yield is outside the selected STCR profile.")
        assert inputs.soil is not None
        soil = inputs.soil.oxide_values()
        if profile.soil_basis == "elemental":
            soil = {"N": soil["N"], "P2O5": soil["P2O5"] / 2.2914, "K2O": soil["K2O"] / 1.2046}
        base = calculate_stcr(inputs.target_yield, soil, profile.coefficients)
        method = f"STCR: {profile.source}; reviewed by {profile.verified_by}"
        kind = "stcr"
    elif ratings is not None and data_dir is not None:
        adjustment = load_ratings(data_dir)["dose_adjustment"]
        factors = {n: adjustment[ratings[n]] for n in NUTRIENTS}
        method = "Soil-test-rating adjusted general recommendation (125/100/75%; not STCR)"
        kind = "rating"
        warnings.append(
            "Doses are the general recommendation scaled by your soil-test ratings. "
            "Target yield is not used; a calibrated STCR equation would be more precise."
        )
    else:
        method = "General recommended dose (no soil test; not STCR)"
        kind = "reference"
        warnings.append(
            "No soil test: the general recommendation is used unchanged. Target yield is not used; "
            "no yield prediction is made."
        )
    if kind != "stcr":
        if inputs.crop in ("rice", "maize"):
            warnings.append(
                "Rice/maize base doses are general Indo-Gangetic recommendations; confirm with KVK."
            )
        else:
            warnings.append(
                "Wheat/sugarcane base doses are transcribed from the project specification."
            )
    if inputs.soil is None:
        warnings.append(
            "No soil test supplied; numeric block averages are unavailable. No soil values were invented."
        )
    credit = dict.fromkeys(NUTRIENTS, 0.0)
    if inputs.fym_t_ha and data_dir is not None:
        per_t = load_ratings(data_dir)["fym"]["credit_kg_per_t"]
        credit = {n: per_t[n] * inputs.fym_t_ha for n in NUTRIENTS}
        warnings.append(
            "FYM credit assumes well-rotted manure and conservative first-season availability."
        )
    per_ha = {n: max(0.0, base[n] * factors[n] - credit[n]) for n in NUTRIENTS}
    breakdown = {
        "kind": kind,
        "base_per_ha": base,
        "factors": factors,
        "ratings": ratings,
        "fym_credit_per_ha": credit,
        "per_ha": per_ha,
    }
    return {n: per_ha[n] * inputs.area_ha for n in NUTRIENTS}, method, warnings, breakdown
