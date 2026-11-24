"""
engine/jalkhadd_bridge.py
─────────────────────────
Thin adapter between krishi's AdvisoryInput / NUTRIENTS convention and the
jal_khadd (ICAR-STCR) engine.

This bridge is inserted at the top of engine/stcr.nutrient_requirement() so
that every crop supported by jal_khadd automatically uses the rigorously
verified ICAR equations. Unsupported crops (e.g. sugarcane) fall through to
krishi's existing reference-dose path.

Nutrient convention differences resolved here:
  jal_khadd  → elemental (N, P, K in kg/ha)
  krishi      → oxide     (N, P2O5, K2O in kg/ha)
"""

from __future__ import annotations

from engine.jalkhadd.equations import REGISTRY, StcrEquation, get_equation
from engine.jalkhadd.planner import dose_and_base
from engine.models import NUTRIENTS, AdvisoryInput

# Conversion factors (same as engine/models.py)
P_TO_P2O5 = 2.2914
K_TO_K2O = 1.2046


def is_supported(crop: str) -> bool:
    """Return True if jal_khadd has a verified ICAR equation for this crop."""
    return crop.strip().lower() in REGISTRY


def _build_soil(inputs: AdvisoryInput) -> dict:
    """
    Build the soil dict jal_khadd expects: elemental values (kg/ha) keyed by
    N, P, K, and OC (organic carbon %) when present.
    """
    if inputs.soil is None:
        raise ValueError(
            "jal_khadd STCR requires soil test values. "
            "Please supply N, P, K from your Soil Health Card."
        )
    el = inputs.soil.elemental_values()  # {N, P, K} in kg/ha
    soil: dict = {"N": el["N"], "P": el["P"], "K": el["K"]}
    if inputs.soil.organic_carbon is not None:
        soil["OC"] = inputs.soil.organic_carbon
    return soil


def _clamp_target(target: float, eq: StcrEquation, warnings: list[str]) -> float:
    """Clamp target yield to the equation's validated range, with a warning."""
    lo, hi = eq.target_range
    if target < lo:
        warnings.append(
            f"Target yield {target:.1f} q/ha is below the validated minimum "
            f"({lo:.1f} q/ha) for the {eq.crop} equation ({eq.centre}). "
            f"Using {lo:.1f} q/ha."
        )
        return lo
    if target > hi:
        warnings.append(
            f"Target yield {target:.1f} q/ha exceeds the validated maximum "
            f"({hi:.1f} q/ha) for the {eq.crop} equation ({eq.centre}). "
            f"Using {hi:.1f} q/ha."
        )
        return hi
    return target


def _manure_credits(fym_t_ha: float, eq: StcrEquation) -> dict[str, float]:
    """
    Compute organic-nitrogen equivalent (kg/ha) per nutrient from FYM.
    Returns zeros if the equation has no manure term.
    """
    zero = {"N": 0.0, "P": 0.0, "K": 0.0}
    if fym_t_ha <= 0:
        return zero
    if not any(eq.c[n] > 0 for n in ("N", "P", "K")):
        return zero
    comp = eq.fym_composition_pct or {}
    return {n: fym_t_ha * 1000.0 * comp.get(n, 0.0) / 100.0 for n in ("N", "P", "K")}


def jalkhadd_nutrient_requirement(
    inputs: AdvisoryInput,
) -> tuple[dict[str, float], str, list[str], dict]:
    """
    Primary entry point called by engine/stcr.nutrient_requirement().

    Returns the same 4-tuple that krishi's existing STCR path returns:
        (total_field_kg, method_str, warnings, breakdown)

    total_field_kg keys: N, P2O5, K2O  (oxide convention, total for the plot)
    """
    eq = get_equation(inputs.crop)
    warnings: list[str] = [
        "Research prototype: have a qualified agronomist (KVK Dhanauri) review before field use."
    ]

    soil = _build_soil(inputs)
    target = _clamp_target(inputs.target_yield, eq, warnings)
    on_kg_ha = _manure_credits(inputs.fym_t_ha, eq)

    if inputs.fym_t_ha > 0 and all(eq.c[n] == 0 for n in ("N", "P", "K")):
        warnings.append(
            "FYM/manure was given, but the ICAR equation for "
            f"{eq.crop} has no manure credit term. Manure NOT subtracted from dose."
        )

    # --- STCR dose (elemental kg/ha) ---
    dose_el, base_el = dose_and_base(eq, soil, target, on_kg_ha)

    # Warn on out-of-range soil values (extrapolation)
    for var, (vlo, vhi) in eq.soil_range.items():
        v = soil.get(var)
        if v is not None and not vlo <= v <= vhi:
            warnings.append(
                f"Soil {var} = {v:.1f} is outside the calibrated range "
                f"({vlo}–{vhi}). The dose is an extrapolation; get expert review."
            )

    # Equation-specific caution from the ICAR compendium
    if eq.caution:
        warnings.append(f"Equation note: {eq.caution}")

    # --- Convert to oxide convention (krishi standard) ---
    def to_oxide(el: dict) -> dict:
        return {
            "N": el["N"],
            "P2O5": el["P"] * P_TO_P2O5,
            "K2O": el["K"] * K_TO_K2O,
        }

    dose_oxide = to_oxide(dose_el)
    base_oxide = to_oxide(base_el)

    # FYM credit contribution alone (base minus soil-test-only component)
    fym_credit_oxide = {
        "N": eq.c["N"] * on_kg_ha["N"],
        "P2O5": eq.c["P"] * on_kg_ha["P"] * P_TO_P2O5,
        "K2O": eq.c["K"] * on_kg_ha["K"] * K_TO_K2O,
    }

    # Total kg required for the plot
    area_ha: float = inputs.area_ha
    total_field_kg: dict[str, float] = {n: dose_oxide[n] * area_ha for n in NUTRIENTS}

    method = (
        f"ICAR STCR — {eq.variety}, {eq.centre} "
        f"[verified against ICAR AICRP-STCR compendium]"
    )

    breakdown = {
        "kind": "stcr",
        # krishi UI reads these keys:
        "base_per_ha": base_oxide,
        "factors": {n: 1.0 for n in NUTRIENTS},
        "ratings": None,
        "fym_credit_per_ha": fym_credit_oxide,
        "per_ha": dose_oxide,
        # extra metadata exposed for the report / debug
        "jalkhadd": {
            "equation_key": eq.key,
            "crop": eq.crop,
            "variety": eq.variety,
            "centre": eq.centre,
            "season": eq.season,
            "target_q_ha": target,
            "target_range": list(eq.target_range),
            "soil_elemental_used": {k: round(v, 3) for k, v in soil.items()},
            "dose_elemental_kg_ha": {k: round(v, 2) for k, v in dose_el.items()},
            "base_elemental_kg_ha": {k: round(v, 2) for k, v in base_el.items()},
            "fym_t_ha": inputs.fym_t_ha,
            "manure_on_kg_ha": on_kg_ha,
            "applicability": eq.applicability,
            "verification": eq.verification,
        },
    }

    return total_field_kg, method, warnings, breakdown
