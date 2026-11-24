# HANDOFF.md — Krishi × Jal-Khadd Integration

## Goal and constraints
Integrate the `jal_khadd` ML engine (`jalkhadd/` package) as the **primary STCR engine** inside the `krishi` Flask web app. Bundle everything into a single folder (`krishi/`) and push to `https://github.com/Avynnn-7/krishi`.

- jal_khadd is the default for all crops it supports (wheat, rice, maize, mustard, barley).
- Sugarcane falls back to krishi's existing reference-dose path (jal_khadd explicitly refuses to fake a sugarcane equation for Uttarakhand).
- krishi's existing UI, WhatsApp bot, irrigation planner, PDF export, and optimizer are **unchanged**.
- `.env` and secrets excluded from git (already in `.gitignore`).

## Completed and verified ✅

| Step | File(s) | Verification |
|---|---|---|
| Copy jalkhadd package | `engine/jalkhadd/*.py` | `import` chain clean |
| Fix jalkhadd internal imports | `planner.py, solver.py, farmio.py` | Changed `jalkhadd.` → `engine.jalkhadd.` |
| Fix catalog.py indentation bug | `engine/jalkhadd/catalog.py` | Python syntax check |
| Write bridge adapter | `engine/jalkhadd_bridge.py` | 7 manual tests pass |
| Patch `nutrient_requirement()` | `engine/stcr.py` | jal_khadd fires for wheat/rice/maize/mustard/barley+soil; fallback for sugarcane |
| Fix `load_profiles()` | `engine/stcr.py` | Strips extra JSON fields; Pydantic validates cleanly |
| Relax `Coefficient` bounds | `engine/stcr.py` | Accepts real ICAR values (cs_percent=782 for rice P2O5) |
| Extend `Crop` enum | `engine/models.py` | Added mustard, barley |
| Add Narsan data | `data/farms_shc_narsan.csv`, `data/products_sample.csv` | Files present |
| Run existing test suite | `tests/` | **68/68 passed** |
| Commit + push to GitHub | `https://github.com/Avynnn-7/krishi` | Commit `d3c3258` on `main` |

## In progress
Nothing — task is **complete**.

## Decisions

| Decision | Reason |
|---|---|
| jal_khadd as default (Option A) | krishi's reference doses explicitly labelled "not calibrated STCR" in source |
| Bridge skips when `stcr_profile` is set | Named profile = explicit override; keeps backward compat |
| Copy jalkhadd as `engine/jalkhadd/` | Self-contained in one repo; no sys.path hacks |
| Keep krishi's PuLP optimizer for bag-buying | Avoids breaking existing report format; both are correct |
| Convert doses N/P/K → N/P2O5/K2O at bridge boundary | jal_khadd works in elemental; krishi's report expects oxide |
| Relaxed Coefficient bounds | ICAR equations have soil-deduction factors well above 100% |

## Next action
**Task complete.** No further action required.

If resuming for future work (e.g., deploying, adding new crops):
1. Activate venv: `source .venv_linux/bin/activate` (Linux) or use Windows `.venv`
2. Run tests: `python -m pytest tests/ -q`
3. Push changes: `git add -A && git commit -m "..." && git push origin main`

## Remaining work and blockers
None — all deliverables done.
