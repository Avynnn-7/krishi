import math
from decimal import Decimal

import pulp

from engine.models import NUTRIENTS, Product, valid_nutrients


class OptimizationError(RuntimeError):
    pass


def optimize(required: dict[str, float], budget: float, products: list[Product]) -> dict:
    """Buy whole bags; allocate partial bags without exceeding nutrient requirements."""
    valid_nutrients(required)
    if not math.isfinite(budget) or budget < 0:
        raise ValueError("Budget must be finite and nonnegative.")
    if not products or len({p.name for p in products}) != len(products):
        raise ValueError("A nonempty catalog with unique names is required.")
    cents = [int(Decimal(str(p.price_rs)) * 100) for p in products]
    budget_cents = int(Decimal(str(budget)) * 100)
    model = pulp.LpProblem("jal_khadd", pulp.LpMaximize)
    bags = [
        pulp.LpVariable(f"bags_{j}", 0, budget_cents // cents[j], cat="Integer")
        for j in range(len(products))
    ]
    applied = [pulp.LpVariable(f"apply_kg_{j}", 0) for j in range(len(products))]
    cost = pulp.lpSum(bags[j] * cents[j] for j in range(len(products)))
    model += cost <= budget_cents
    for j, product in enumerate(products):
        model += applied[j] <= bags[j] * product.weight_kg
    supplied = {
        n: pulp.lpSum(applied[j] * p.fraction(n) for j, p in enumerate(products)) for n in NUTRIENTS
    }
    active = [n for n in NUTRIENTS if required[n] > 1e-8]
    floor = pulp.LpVariable("minimum_coverage", 0, 1)
    for n in NUTRIENTS:
        model += supplied[n] <= required[n]
        if n in active:
            model += supplied[n] >= floor * required[n]
    if not active:
        model += floor == 1
    solver = pulp.PULP_CBC_CMD(
        msg=False,
        timeLimit=10,
        threads=0,
        gapRel=0,
        options=["randomSeed 42", "randomCbcSeed 42"],
    )

    def solve(objective: pulp.LpAffineExpression | pulp.LpVariable, sense: int) -> float:
        model.sense = sense
        model.setObjective(objective)
        try:
            status = model.solve(solver)
        except pulp.PulpSolverError as exc:
            raise OptimizationError("CBC solver is unavailable or failed to execute.") from exc
        if status != pulp.LpStatusOptimal or model.sol_status != pulp.LpSolutionOptimal:
            raise OptimizationError(
                "The bag optimizer did not reach an optimal solution. Try again."
            )
        return float(pulp.value(objective) or 0)

    best_floor = solve(floor, pulp.LpMaximize)
    model += floor >= max(0, best_floor - 1e-7)
    coverage = pulp.lpSum(supplied[n] / required[n] for n in active)
    best_coverage = solve(coverage, pulp.LpMaximize)
    model += coverage >= max(0, best_coverage - 1e-7)
    best_cost = solve(cost, pulp.LpMinimize)
    model += cost <= round(best_cost)
    solve(pulp.lpSum(applied), pulp.LpMinimize)

    rows = []
    delivered = dict.fromkeys(NUTRIENTS, 0.0)
    for j, product in enumerate(products):
        count = round(bags[j].value() or 0)
        kg = max(0.0, float(applied[j].value() or 0))
        nutrients = {n: kg * product.fraction(n) for n in NUTRIENTS}
        for n in NUTRIENTS:
            delivered[n] += nutrients[n]
        rows.append(
            {
                "product": product.name,
                "bags": count,
                "bag_weight_kg": product.weight_kg,
                "cost": count * cents[j] / 100,
                "purchased_kg": count * product.weight_kg,
                "apply_kg": kg,
                "leftover_kg": max(0, count * product.weight_kg - kg),
                "nutrients": nutrients,
            }
        )
    total = sum(round(row["cost"] * 100) for row in rows) / 100
    if total > budget or any(delivered[n] > required[n] + 1e-4 for n in NUTRIENTS):
        raise OptimizationError("Optimizer output failed budget or nutrient validation.")
    ratios = {n: min(1, delivered[n] / required[n]) if required[n] else 1 for n in NUTRIENTS}
    return {
        "shopping": rows,
        "total_cost": total,
        "budget_remaining": round(budget - total, 2),
        "delivered": delivered,
        "required": required,
        "coverage": ratios,
        "minimum_coverage": min(ratios.values()),
        "shortfall": {n: max(0, required[n] - delivered[n]) for n in NUTRIENTS},
    }
