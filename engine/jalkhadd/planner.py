"""Farm-level planner: soil test + equation + catalogue + budget  ->  dose, bag list, Liebig attainable target."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from engine.jalkhadd.catalog import Product
from engine.jalkhadd.equations import NUTRIENTS, StcrEquation
from engine.jalkhadd.solver import Problem, solve

P_TO_P2O5, K_TO_K2O = 2.2914, 1.2046  # element -> oxide mass factors
OUT_NAME = {"N": "N", "P": "P2O5", "K": "K2O"}


@dataclass
class Settings:
    pk_basis: str = "as_printed"  # "as_printed": card P,K used as printed | "oxide": card P,K converted to P2O5,K2O first
    basis_confirmed: bool = False  # set True once GBPUAT/KVK confirms the soil-test basis of the equation
    min_bag_area_ha: float = 0.1  # smaller plots get loose kg, not whole bags
    default_target: float | None = None  # q/ha; None = low end of the equation's validated range
    price_per_q: float | None = None  # Rs per quintal, only used by the target scan


@dataclass
class Farm:
    farm_id: str
    crop: str
    area_ha: float
    soil: dict  # keys among N (KMnO4-N), P (Olsen-P), K (NH4OAc-K) in kg/ha, OC in %, optional S in ppm
    fym_t_ha: float = 0.0
    target_q_ha: float | None = None
    budget_rs: float | None = None
    applied_kg: dict = field(default_factory=dict)  # product name -> kg applied on the whole field last season
    notes: list = field(default_factory=list)


def _need(farm: Farm, var: str) -> float:
    v = farm.soil.get(var)
    if v is None or not math.isfinite(v) or v < 0:
        raise ValueError(f"missing or invalid soil value '{var}'")
    return float(v)


def dose_and_base(eq: StcrEquation, soil: dict, target: float, on_kg_ha: dict) -> tuple[dict, dict]:
    """(dose kg/ha, base kg/ha) per nutrient; base = b*S + c*ON is what soil and manure already supply."""
    base = {n: eq.b[n] * soil[eq.soil_var[n]] + eq.c[n] * on_kg_ha[n] for n in NUTRIENTS}
    dose = {n: max(0.0, eq.a[n] * target - base[n]) for n in NUTRIENTS}
    return dose, base


def plan_farm(farm: Farm, eq: StcrEquation, products: list, settings: Settings | None = None,
              budget_override: float | None = None) -> dict:
    s = settings or Settings()
    if not (math.isfinite(farm.area_ha) and farm.area_ha > 0):
        raise ValueError("area must be positive")
    target = farm.target_q_ha if farm.target_q_ha is not None else (
        s.default_target if s.default_target is not None else eq.target_range[0])
    lo, hi = eq.target_range
    if not lo <= target <= hi:
        raise ValueError(f"target {target:g} q/ha is outside the {lo:g}-{hi:g} q/ha range this {eq.crop} equation was "
                         f"validated for")
    if s.pk_basis not in ("as_printed", "oxide"):
        raise ValueError("pk_basis must be 'as_printed' or 'oxide'")

    warnings = list(farm.notes)
    soil = {k: float(v) for k, v in farm.soil.items() if v is not None}
    for var in {eq.soil_var[n] for n in NUTRIENTS}:
        _need(farm, var)
    if s.pk_basis == "oxide":
        soil["P"] *= P_TO_P2O5
        soil["K"] *= K_TO_K2O
    if not s.basis_confirmed:
        warnings.append("P/K soil-test basis of the equation (element vs oxide) is unconfirmed; result computed with "
                        f"pk_basis='{s.pk_basis}'. Confirm with GBPUAT/KVK before field use.")
    for var, (vlo, vhi) in eq.soil_range.items():
        v = soil.get(var)
        if v is not None and not vlo <= v <= vhi:
            warnings.append(f"Soil {var} = {v:g} is outside the range this equation was calibrated on ({vlo:g}-{vhi:g}): "
                            f"the dose is an extrapolation; get expert review.")
    s_ppm = farm.soil.get("S")
    if s_ppm is not None and s_ppm < 10:
        warnings.append(f"Sulphur {s_ppm:g} ppm is below the Soil Health Card limit of 10: the engine has no STCR equation "
                        f"for sulphur; add an S-bearing product by hand (e.g. SSP supplies 11% S).")

    on = dict.fromkeys(NUTRIENTS, 0.0)
    if farm.fym_t_ha > 0:
        if any(eq.c[n] > 0 for n in NUTRIENTS):
            on = {n: farm.fym_t_ha * 1000.0 * eq.fym_composition_pct[n] / 100.0 for n in NUTRIENTS}
        else:
            warnings.append("Manure given, but this equation has no manure term: manure NOT credited (dose is for fertilizer "
                            "alone).")
    dose, base = dose_and_base(eq, soil, target, on)
    cap = {n: dose[n] * farm.area_ha for n in NUTRIENTS}
    budget = budget_override if budget_override is not None else farm.budget_rs
    mode = "bags" if farm.area_ha >= s.min_bag_area_ha else "loose"
    if mode == "loose":
        warnings.append(f"Plot is under {s.min_bag_area_ha:g} ha: quantities are loose kg (buy from a shared or partial bag).")

    def run(b):
        return solve(Problem(products, dict(eq.a), base, target, farm.area_ha, cap, b, mode))

    sol = run(budget)
    short = {n: max(0.0, cap[n] - sol["delivered_kg"][n]) for n in NUTRIENTS}
    full_cost = None
    if max(short.values()) <= 1e-4:
        status = "target_met"
    elif budget is not None and max((cap[n] - run(None)["delivered_kg"][n]) for n in NUTRIENTS) <= 1e-4:
        status = "budget_limited"
        full_cost = run(None)["cost_rs"]
    else:
        status = "catalogue_limited"
        missing = [OUT_NAME[n] for n in NUTRIENTS if cap[n] - run(None)["delivered_kg"][n] > 1e-4]
        warnings.append(f"No product in the catalogue can supply the full {', '.join(missing)} dose.")

    lines = []
    for j, pr in enumerate(products):
        kg = sol["applied_kg"][j]
        nb = sol["bags"][j] if sol["bags"] else None
        if (nb or 0) > 0 or kg > 1e-6:
            lines.append({
                "product": pr.name, "bags": nb, "bag_kg": pr.weight_kg,
                "buy_kg": nb * pr.weight_kg if nb is not None else kg, "apply_kg": kg,
                "leftover_kg": (nb * pr.weight_kg - kg) if nb is not None else 0.0,
                "cost_rs": (nb * pr.price_rs) if nb is not None else kg / pr.weight_kg * pr.price_rs,
            })
    out = {
        "farm_id": farm.farm_id, "crop": eq.crop, "equation": f"{eq.variety}, {eq.centre}", "area_ha": farm.area_ha,
        "target_q_ha": target, "status": status, "mode": mode, "pk_basis": s.pk_basis,
        "soil_used": {k: round(v, 3) for k, v in soil.items()},
        "dose_kg_ha": {OUT_NAME[n]: dose[n] for n in NUTRIENTS},
        "required_kg": {OUT_NAME[n]: cap[n] for n in NUTRIENTS},
        "delivered_kg": {OUT_NAME[n]: sol["delivered_kg"][n] for n in NUTRIENTS},
        "shortfall_kg": {OUT_NAME[n]: short[n] for n in NUTRIENTS},
        "attainable_target_q_ha": sol["attainable_target"],
        "limiting_nutrient": (min(NUTRIENTS, key=lambda n: (sol["delivered_kg"][n] / farm.area_ha + base[n]) / eq.a[n])
                              if status != "target_met" else None),
        "purchase": lines, "total_cost_rs": sol["cost_rs"], "budget_rs": budget,
        "budget_remaining_rs": None if budget is None else budget - sol["cost_rs"],
        "full_plan_cost_rs": full_cost, "warnings": warnings,
        "equation_caution": eq.caution,
    }
    if out["limiting_nutrient"]:
        out["limiting_nutrient"] = OUT_NAME[out["limiting_nutrient"]]
    if farm.applied_kg:
        out["practice"] = compare_practice(farm, products, dose, cap, out)
    return out


def compare_practice(farm: Farm, products: list, dose: dict, cap: dict, plan: dict) -> dict:
    """What the farmer actually applied vs the STCR dose. Reports over/under-application and the Liebig limiting nutrient
    (lowest coverage); it makes NO yield claim, because the response below the validated target is not calibrated."""
    by = {p.name: p for p in products}
    deliv = dict.fromkeys(NUTRIENTS, 0.0)
    cost = 0.0
    for name, kg in farm.applied_kg.items():
        if name not in by:
            raise ValueError(f"applied product '{name}' is not in the catalogue")
        cost += kg / by[name].weight_kg * by[name].price_rs
        for n in NUTRIENTS:
            deliv[n] += kg * by[name].fraction(n)
    per_ha = {n: deliv[n] / farm.area_ha for n in NUTRIENTS}
    cov = {OUT_NAME[n]: (per_ha[n] / dose[n] if dose[n] > 1e-9 else None) for n in NUTRIENTS}
    vals = {k: v for k, v in cov.items() if v is not None}
    return {
        "applied_kg_ha": {OUT_NAME[n]: per_ha[n] for n in NUTRIENTS},
        "minus_stcr_dose_kg_ha": {OUT_NAME[n]: per_ha[n] - dose[n] for n in NUTRIENTS},
        "coverage_of_dose": cov,
        "least_covered_nutrient": min(vals, key=vals.get) if vals else None,
        "cost_rs": cost, "cost_minus_plan_rs": cost - plan["total_cost_rs"],
    }


def scan_targets(farm: Farm, eq: StcrEquation, products: list, settings: Settings | None = None, step: float = 1.0) -> list:
    """Plan at each target in the validated range: purchase cost and the cost of each extra quintal of target.
    Valid under the STCR assumption that the doses deliver their target (validated within +/-10% in field trials)."""
    s = settings or Settings()
    lo, hi = eq.target_range
    ts, t = [], lo
    while t <= hi + 1e-9:
        ts.append(round(t, 6))
        t += step
    rows, prev = [], None
    for t in ts:
        f = replace(farm, target_q_ha=t)
        r = plan_farm(f, eq, products, s)
        row = {"target_q_ha": t, "cost_rs": r["total_cost_rs"], "status": r["status"],
               "dose_kg_ha": r["dose_kg_ha"], "extra_cost_per_extra_q_rs": None}
        if prev is not None and (t - prev["target_q_ha"]) > 0:
            row["extra_cost_per_extra_q_rs"] = (row["cost_rs"] - prev["cost_rs"]) / ((t - prev["target_q_ha"]) * farm.area_ha)
        rows.append(row)
        prev = row
    return rows
