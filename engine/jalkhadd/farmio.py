"""Reading farms from CSV and writing plans (JSON, CSV, farmer-readable Markdown)."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

from engine.jalkhadd.planner import Farm

_NUM = {
    "N": ("soil_n", "n"), "P": ("soil_p", "p"), "K": ("soil_k", "k"), "OC": ("soil_oc", "oc"),
    "S": ("soil_s_ppm", "s"),
}


def _f(v):
    if v is None or str(v).strip() == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def load_farms(path: str, default_crop: str | None = None) -> list[Farm]:
    """Columns (case-insensitive): farm_id | file | survey_no, crop, area_ha, soil_N|N, soil_P|P, soil_K|K, [soil_OC|OC],
    [soil_S_ppm|S], [fym_t_ha], [target_q_ha], [budget_rs], [applied_kg_<ProductName> ...]."""
    farms, seen = [], {}
    with open(path, encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for i, raw in enumerate(reader, 1):
            r = {k.strip().lower(): v for k, v in raw.items() if k}
            fid = (r.get("farm_id") or "").strip() or (Path(r["file"]).stem if r.get("file") else "") \
                or (f"survey{r['survey_no']}" if r.get("survey_no") else f"farm{i}")
            crop = (r.get("crop") or default_crop or "").strip()
            if not crop:
                raise ValueError(f"{path} row {i}: no crop (add a 'crop' column or pass --crop)")
            soil = {}
            for key, names in _NUM.items():
                for nm in names:
                    if _f(r.get(nm)) is not None:
                        soil[key] = _f(r[nm])
                        break
            notes = []
            sig = tuple(soil.get(k) for k in ("N", "P", "K", "OC"))
            if None not in sig[:3]:
                if sig in seen:
                    notes.append(f"Soil values are identical to farm '{seen[sig]}': possible duplicate card, check before use.")
                else:
                    seen[sig] = fid
            applied = {k[len("applied_kg_"):]: _f(v) for k, v in raw.items()
                       if k and k.lower().startswith("applied_kg_") and _f(v)}
            farms.append(Farm(
                farm_id=fid, crop=crop, area_ha=_f(r.get("area_ha")) or float("nan"), soil=soil,
                fym_t_ha=_f(r.get("fym_t_ha")) or 0.0, target_q_ha=_f(r.get("target_q_ha")),
                budget_rs=_f(r.get("budget_rs")), applied_kg=applied, notes=notes,
            ))
    return farms


def _fmt(x, nd=0):
    return f"{x:,.{nd}f}"


def write_outputs(results: list[dict], outdir: str) -> dict:
    os.makedirs(outdir, exist_ok=True)
    paths = {k: os.path.join(outdir, v) for k, v in
             {"json": "plans.json", "summary": "plans_summary.csv", "lines": "plans_purchase_lines.csv", "md": "plans.md"}.items()}
    with open(paths["json"], "w", encoding="utf-8") as jf:
        json.dump(results, jf, indent=2, ensure_ascii=False)

    with open(paths["summary"], "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["farm_id", "crop", "area_ha", "target_q_ha", "status", "dose_N_kg_ha", "dose_P2O5_kg_ha", "dose_K2O_kg_ha",
                    "attainable_target_q_ha", "total_cost_rs", "purchase", "warnings"])
        for r in results:
            if r.get("status") == "error":
                w.writerow([r["farm_id"], r.get("crop", ""), "", "", "error", "", "", "", "", "", "", r["error"]])
                continue
            buy = "; ".join(f"{l['product']} x{l['bags']}" if l["bags"] is not None else f"{l['product']} {l['buy_kg']:.1f} kg"
                            for l in r["purchase"]) or "none"
            d = r["dose_kg_ha"]
            w.writerow([r["farm_id"], r["crop"], r["area_ha"], r["target_q_ha"], r["status"], round(d["N"]), round(d["P2O5"]),
                        round(d["K2O"]), round(r["attainable_target_q_ha"], 1), round(r["total_cost_rs"]), buy,
                        " | ".join(r["warnings"])])

    with open(paths["lines"], "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["farm_id", "product", "bags", "bag_kg", "buy_kg", "apply_kg", "leftover_kg", "cost_rs"])
        for r in results:
            for l in r.get("purchase", []):
                w.writerow([r["farm_id"], l["product"], "" if l["bags"] is None else l["bags"], l["bag_kg"],
                            round(l["buy_kg"], 2), round(l["apply_kg"], 2), round(l["leftover_kg"], 2), round(l["cost_rs"], 2)])

    md = ["# Fertilizer plans (STCR dose + whole-bag purchase)\n",
          "Doses come from ICAR AICRP-STCR equations. They are recommendations to be reviewed by an agronomist (KVK), not "
          "guarantees of yield or profit.\n"]
    for r in results:
        if r.get("status") == "error":
            md.append(f"## {r['farm_id']}\n**Could not plan:** {r['error']}\n")
            continue
        d = r["dose_kg_ha"]
        head = {"target_met": "target can be met", "budget_limited": "BUDGET TOO LOW for the full plan",
                "catalogue_limited": "NO PRODUCT for part of the dose"}[r["status"]]
        md.append(f"## {r['farm_id']} - {r['crop']}, {r['area_ha']:g} ha, target {r['target_q_ha']:g} q/ha ({head})")
        md.append(f"- Soil used: " + ", ".join(f"{k} {v:g}" for k, v in r["soil_used"].items()))
        md.append(f"- Apply per hectare: **N {d['N']:.0f}**, **P2O5 {d['P2O5']:.0f}**, **K2O {d['K2O']:.0f}** kg")
        if r["purchase"]:
            md.append("- Buy:")
            for l in r["purchase"]:
                what = f"{l['bags']} bag(s) of {l['bag_kg']:g} kg" if l["bags"] is not None else f"{l['buy_kg']:.1f} kg loose"
                md.append(f"  - {l['product']}: {what}; apply {l['apply_kg']:.1f} kg; Rs {_fmt(l['cost_rs'])}")
        else:
            md.append("- Buy: nothing (soil already supplies the target)")
        md.append(f"- **Total cost: Rs {_fmt(r['total_cost_rs'])}**" +
                  (f" (budget Rs {_fmt(r['budget_rs'])}, left Rs {_fmt(r['budget_remaining_rs'])})" if r["budget_rs"] else ""))
        if r["status"] != "target_met":
            md.append(f"- Attainable target with this budget/catalogue: {r['attainable_target_q_ha']:.1f} q/ha; limiting "
                      f"nutrient (Liebig): {r['limiting_nutrient']}. Shortfall kg: " +
                      ", ".join(f"{k} {v:.1f}" for k, v in r["shortfall_kg"].items() if v > 1e-4))
            if r.get("full_plan_cost_rs") is not None:
                md.append(f"- Full plan would cost Rs {_fmt(r['full_plan_cost_rs'])}")
        if "practice" in r:
            p = r["practice"]
            md.append("- Farmer's practice vs STCR dose (kg/ha): " + ", ".join(
                f"{k} {v:+.0f}" for k, v in p["minus_stcr_dose_kg_ha"].items()) + f"; cost Rs {_fmt(p['cost_rs'])}")
        for wmsg in r["warnings"]:
            md.append(f"- WARNING: {wmsg}")
        md.append("")
    with open(paths["md"], "w", encoding="utf-8") as mf:
        mf.write("\n".join(md))
    return paths
