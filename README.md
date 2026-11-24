# Krishi — Jal-Khadd Agronomic Advisory System

> **Soil-test–targeted fertilizer planning for Haridwar district farmers.**
> Built for the Community Outreach course project, IIT Roorkee.
> Field-tested at **Narsan village**, Haridwar.

A bilingual (Hindi/English) Flask web application + WhatsApp bot implementing
precision fertilizer recommendations using **ICAR AICRP-STCR verified equations**,
integer-linear-program bag optimization, and FAO-56 irrigation planning.

---

## ⚡ Run locally (Linux / Mac)

Python 3.11+ required. Tested on Python 3.12.

```bash
# 1. Clone
git clone https://github.com/Avynnn-7/krishi.git
cd krishi

# 2. Create virtual environment and install
python3 -m venv .venv
source .venv/bin/activate
pip install "pulp>=3.0,<4" -r requirements.txt   # pin PuLP 3.x (PuLP 4 has breaking API changes)

# 3. Compile Hindi translations
pybabel compile -d translations

# 4. Copy env template (then edit if you have Meta/Twilio keys)
cp .env.example .env

# 5. Start
flask --app "app:create_app" run --host 127.0.0.1 --port 5050
```

Open **http://127.0.0.1:5050**

The app works fully without any API keys — weather, WhatsApp alerts and SMS are
the only features that need credentials. CBC LP solver ships with PuLP.

---

## ⚡ Run locally (Windows)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install "pulp>=3.0,<4" -r requirements.txt
pybabel compile -d translations
copy .env.example .env
flask --app "app:create_app" run --host 127.0.0.1 --port 5050
```

---

## What runs without credentials

| Feature | Status |
|---|---|
| Advisory form (ICAR STCR dose + bag plan) | ✅ fully local |
| Soil Health Card interpretation | ✅ fully local |
| Irrigation planner (FAO-56) | ✅ fully local |
| PDF export, calendar (.ics), JSON | ✅ fully local |
| Scenario / simulator | ✅ fully local |
| Village soil hub (Narsan data included) | ✅ fully local |
| Hindi/English bilingual UI | ✅ fully local |
| Weather-based postponement | ⚡ optional (Open-Meteo, free, no key needed) |
| WhatsApp bot (Meta Cloud API) | 🔑 needs META_* keys in .env |
| SMS alerts (Twilio) | 🔑 needs TWILIO_* keys in .env |

---

## Project structure

```
krishi/
├── app.py                    # Flask app factory, all routes
├── engine/
│   ├── jalkhadd/             # ← PRIMARY ML ENGINE (ICAR AICRP-STCR)
│   │   ├── equations.py      #   STCR equations (wheat/rice/maize/mustard/barley)
│   │   ├── planner.py        #   Farm → dose + bag plan
│   │   ├── solver.py         #   PuLP ILP (Liebig attainable target)
│   │   ├── catalog.py        #   Fertilizer products
│   │   ├── farmio.py         #   CSV batch I/O
│   │   └── shc.py            #   Soil Health Card PDF parser
│   ├── jalkhadd_bridge.py    # Adapter: krishi ↔ jal_khadd
│   ├── stcr.py               # STCR orchestrator (uses jal_khadd as primary)
│   ├── optimizer.py          # PuLP bag optimizer
│   ├── service.py            # Advisory orchestrator
│   ├── irrigation.py         # FAO-56 water planner
│   ├── soil_card.py          # SHC interpretation
│   ├── recommendations.py    # Bilingual action engine
│   └── models.py             # Pydantic data models
├── bot/                      # WhatsApp bot (Meta Cloud API)
├── data/
│   ├── farms_shc_narsan.csv  # Narsan village Soil Health Card data
│   ├── stcr_coefficients.json
│   ├── fertilizer_catalog.json
│   └── ...
├── templates/                # Jinja2 HTML templates
├── static/                   # CSS, JS, fonts
├── translations/             # Flask-Babel i18n (en, hi)
├── tests/                    # Pytest suite (68 tests)
└── HANDOFF.md                # Session continuity document
```

---

## ICAR STCR Engine — how it works

The primary engine (`engine/jalkhadd/`) implements the **Soil Test Crop Response**
targeted-yield approach from the ICAR AICRP-STCR compendium *"Four Decades of
STCR Research"*.

**Formula per nutrient:**

```
Fertilizer dose (kg/ha) = a × T  −  b × S  −  c × M   (floored at 0)
```

Where:
- `T` = yield target (q/ha)
- `S` = soil-test value (kg/ha, from Soil Health Card)
- `M` = manure nutrient supplied (kg/ha, from FYM input)
- `a, b, c` = ICAR-verified coefficients per crop per nutrient

Verified crops: **wheat** (GBPUAT Pantnagar), **rice** (IARI Delhi),
**maize** (GBPUAT Pantnagar), **mustard** (GBPUAT Pantnagar), **barley** (GBPUAT Pantnagar)

After computing doses, a **PuLP Integer Linear Program** solves for the minimum-cost
whole-bag purchase that meets the dose, subject to the farmer's budget. If budget is
insufficient it reports the best attainable yield (Liebig's Law of the Minimum) and
the limiting nutrient.

---

## Community outreach context

| Activity | Outcome |
|---|---|
| KVK Dhanauri meeting | Identified priority crops and local equation sources |
| Narsan village data collection | 20+ Soil Health Cards; data in `data/farms_shc_narsan.csv` |
| Farmer workshop | Demonstrated advisory, collected feedback on Hindi UI |
| Website + WhatsApp bot | Local-only prototype; runs on this codebase |

---

## Tests

```bash
pytest tests/ -q
# 68 passed
```

---

## Team

Developed as part of the Community Outreach course (3rd year, IIT Roorkee).
Data sourced from Agriculture Office Haridwar and KVK Dhanauri.
STCR equations from ICAR AICRP-STCR compendium — verified against ready-reckoner tables.
