"""Whole-bag ILP with Liebig's Law of the Minimum applied to the STCR equation.

STCR inverted per nutrient gives the yield target each nutrient can carry:

        T_n = ( F_n / area + b_n*S_n + c_n*ON_n ) / a_n          F_n = nutrient delivered to the field (kg)

Liebig: attainable target  T_att = min_n T_n   (the scarcest nutrient decides).  We solve, in order:

  1. maximise T_att                      s.t. budget, whole bags, and F_n <= STCR dose (never over-apply a nutrient)
  2. minimise purchase cost              s.t. T_att at its optimum
  3. minimise kg applied                 s.t. that cost       (tie-break: least handling / least over-supply)

With a sufficient budget and catalogue, step 1 reaches the full target and the plan is the cheapest whole-bag purchase that
delivers exactly the STCR dose. With a binding budget it maximises the attainable target and reports the shortfall.
Constraints are written in q/ha units (unit-free), so very small requirements do not hit solver tolerances.
Purchased bags are integer; the applied amount is continuous and may be less than the bags bought (leftover reported).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pulp

from engine.jalkhadd.catalog import Product

NUT = ("N", "P", "K")

# PuLP 4.0 compatibility: use COIN_CMD if available, else fall back to PULP_CBC_CMD.
_SOLVER_CLS = getattr(pulp, "COIN_CMD", None) or pulp.PULP_CBC_CMD
# PuLP 4.0 moves LpVariable construction to prob.add_variable; detect availability.
_HAS_ADD_VARIABLE = hasattr(pulp.LpProblem, "add_variable")


def _add_var(prob, name, low=0, up=None, cat="Continuous"):
    """Create a variable compatible with both PuLP 3.x and 4.x."""
    if _HAS_ADD_VARIABLE:
        return prob.add_variable(name, lowBound=low, upBound=up, cat=cat)
    return pulp.LpVariable(name, low, up, cat=cat)


class SolverError(RuntimeError):
    pass


@dataclass
class Problem:
    products: list
    a: dict  # kg nutrient per q/ha of target
    base: dict  # kg/ha already supplied by soil + manure: b*S + c*ON
    target: float  # q/ha
    area_ha: float
    cap_kg: dict  # field-level maximum kg per nutrient = STCR dose * area
    budget_rs: float | None  # None = unlimited
    mode: str = "bags"  # "bags" (whole bags) or "loose" (kg, for plots too small for a bag)


def _applied_ub(prod: Product, cap_kg: dict) -> float:
    lim = math.inf
    for n in NUT:
        f = prod.fraction(n)
        if f > 0:
            lim = min(lim, cap_kg[n] / f)  # applying more would exceed some nutrient's dose
    return 0.0 if lim == math.inf else lim  # a product with no N/P/K is of no use to this problem


def solve(p: Problem) -> dict:
    prods: list[Product] = p.products
    J = range(len(prods))
    ub = [_applied_ub(pr, p.cap_kg) for pr in prods]
    cents = [round(pr.price_rs * 100) for pr in prods]
    budget_c = None if p.budget_rs is None else int(round(p.budget_rs * 100))

    prob = pulp.LpProblem("jalkhadd", pulp.LpMaximize)
    app = [_add_var(prob, f"app_{j}", 0, ub[j]) for j in J]
    if p.mode == "bags":
        bags = [_add_var(prob, f"bags_{j}", 0, math.ceil(ub[j] / prods[j].weight_kg - 1e-9), cat="Integer") for j in J]
        for j in J:
            prob += app[j] <= prods[j].weight_kg * bags[j]
        cost = pulp.lpSum(cents[j] * bags[j] for j in J)
    elif p.mode == "loose":
        bags = None
        cost = pulp.lpSum(cents[j] / prods[j].weight_kg * app[j] for j in J)
    else:
        raise ValueError(f"unknown mode {p.mode!r}")
    if budget_c is not None:
        prob += cost <= budget_c

    F = {n: pulp.lpSum(prods[j].fraction(n) * app[j] for j in J) for n in NUT}
    tatt = _add_var(prob, "tatt", 0, p.target)
    for n in NUT:
        prob += F[n] <= p.cap_kg[n]
        prob += p.a[n] * p.area_ha * tatt - F[n] <= p.base[n] * p.area_ha  # tatt <= T_n

    solver = _SOLVER_CLS(msg=False, timeLimit=60, gapRel=0, options=["randomSeed 42", "randomCbcSeed 42"])

    def run(obj, sense):
        prob.sense = sense
        prob.setObjective(obj)
        try:
            status = prob.solve(solver)
        except pulp.PulpSolverError as e:
            raise SolverError("CBC solver is unavailable or failed to run.") from e
        if status != pulp.LpStatusOptimal or prob.sol_status != pulp.LpSolutionOptimal:
            raise SolverError("The bag solver did not reach an optimal solution.")
        return float(pulp.value(obj) or 0.0)

    best_t = run(tatt, pulp.LpMaximize)
    prob += tatt >= best_t - 1e-6
    best_cost = run(cost, pulp.LpMinimize)
    prob += cost <= (round(best_cost) if p.mode == "bags" else best_cost + 1e-3)
    run(pulp.lpSum(app), pulp.LpMinimize)

    applied = [max(0.0, float(v.value() or 0.0)) for v in app]
    n_bags = [int(round(v.value() or 0)) for v in bags] if bags else None
    total_cents = (sum(n_bags[j] * cents[j] for j in J) if n_bags is not None
                   else sum(cents[j] / prods[j].weight_kg * applied[j] for j in J))

    # independent check of the returned plan (never trust the solver blindly)
    delivered = {n: sum(prods[j].fraction(n) * applied[j] for j in J) for n in NUT}
    for n in NUT:
        if delivered[n] > p.cap_kg[n] + 1e-6 * max(1.0, p.cap_kg[n]):
            raise SolverError(f"plan exceeds the {n} dose")
    if budget_c is not None and total_cents > budget_c + 1e-6:
        raise SolverError("plan exceeds the budget")
    if n_bags is not None and any(applied[j] > n_bags[j] * prods[j].weight_kg + 1e-6 for j in J):
        raise SolverError("plan applies more than the bags bought")
    t_att = min(p.target, min((delivered[n] / p.area_ha + p.base[n]) / p.a[n] for n in NUT))
    return {"applied_kg": applied, "bags": n_bags, "cost_rs": total_cents / 100.0, "delivered_kg": delivered,
            "attainable_target": t_att}
