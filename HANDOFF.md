# HANDOFF.md — Krishi × Jal-Khadd Integration

## Goal and constraints
Integrate the `jal_khadd` ML engine (`jalkhadd/` package) as the **primary STCR engine** inside the `krishi` Flask web app. Bundle everything into a single folder (`krishi/`) and push to `https://github.com/Avynnn-7/krishi`.

- jal_khadd becomes the default for all crops it supports (wheat, rice, maize, mustard, barley).
- Sugarcane falls back to krishi's existing reference-dose path (jal_khadd explicitly refuses to fake a sugarcane equation for Uttarakhand).
- krishi's existing UI, WhatsApp bot, irrigation planner, PDF export, and optimizer are **unchanged**.
- `.env` and secrets are excluded from git (already in `.gitignore`).

## Completed and verified

_(updated as work progresses)_

- [ ] HANDOFF.md written and readable at `krishi/HANDOFF.md`

## In progress

**Step 1 — Copy jalkhadd package** into `krishi/engine/jalkhadd/`

## Decisions

| Decision | Reason |
|---|---|
| jal_khadd as default (Option A) | krishi's reference doses are explicitly labelled "not calibrated STCR" in source; jal_khadd equations are ICAR-verified per compendium |
| Copy jalkhadd as sub-package of engine/ | Avoids sys.path hacks; keeps everything self-contained in one repo |
| Keep krishi's PuLP optimizer for bag-buying | krishi's optimizer also maximises coverage, well-tested; avoids breaking existing report format |
| Convert doses N/P/K → N/P2O5/K2O at bridge boundary | jal_khadd works in elemental; krishi's report format expects oxide |
| Bridge inserted at top of `nutrient_requirement()` | Minimal invasive change; maintains fallback for unsupported crops |

## Next action

A new agent should:
1. Read this file.
2. Check which steps in "Completed and verified" are ticked.
3. Resume from "In progress" — the exact step and file are listed there.
4. After completing each step, tick it and update "In progress".

## Remaining work and blockers

1. Copy `jal_khadd/jalkhadd/*.py` → `krishi/engine/jalkhadd/`
2. Write `krishi/engine/jalkhadd_bridge.py`
3. Patch `krishi/engine/stcr.py` — insert jalkhadd bridge call at top of `nutrient_requirement()`
4. Copy Narsan data files → `krishi/data/`
5. Run `python -m pytest tests/ -x -q` inside krishi to verify no regressions
6. Set git remote to `https://github.com/Avynnn-7/krishi` and push
7. Update this file with ✓ for each completed step

**Blockers**: GitHub credentials (SSH key or token) must be configured for push to succeed. If push fails, the agent should report the error and ask the user for credentials.
