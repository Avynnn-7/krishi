# Jal-Khadd (जल-खाद) — Technical Specification & Build Roadmap

> **Purpose of this document**: This is the single source of truth for the entire project. If you are a new team member, a collaborator, or a committee reviewer, reading this document will give you complete context on what we are building, why, with what data, and how.

> **Implementation status — 20 October 2026:** A runnable research prototype now accompanies this roadmap. See [README](README.md) for setup, implemented features, data readiness, validation and deployment. Local STCR coefficients, numeric soil averages and official Warabandi records remain pending; reference demonstrations are explicitly labeled and require expert review. The implementation does not claim the sample yields/savings, institutional endorsement, live WhatsApp pricing or automatic next-cycle safety illustrated below. Purchased bags and actual application allocations are reported separately. Garhwali/voice support, verified data import and production authentication/PostgreSQL remain future work. **Update 22 Oct 2026:** personal action plans, Soil Health Card interpretation, soil-rating dose scaling, current-practice comparison, an FAO-56 irrigation planner (depth, litres per bigha, m³, pump hours, canal-turn check) and an irrigation-method comparison with advantages/disadvantages were added.

---

## 1. Project Context

### 1.1 What is this?
A **web application + WhatsApp bot** that gives small farmers in the Haridwar–Roorkee belt a personalised, budget-aware, weather-synced, irrigation-timed fertilizer recommendation — converting complex agricultural science into a simple shopping list and calendar.

### 1.2 Who is this for?
- **Primary users**: KVK scientists, Krishi Mitras (progressive farmer-volunteers), extension workers — they operate the tool and relay advice to farmers
- **Secondary users**: Younger-generation farmers (20s–30s) who can use a smartphone browser directly
- **Tertiary users**: Gram Pradhans who can use the WhatsApp bot to get a quick advisory for their village

### 1.3 Course & Team
- **Course**: Community Outreach (CORE) — XXC-399, 3rd Year UG, IIT Roorkee
- **Department**: Mathematics
- **Team size**: 6 members
- **Required hours**: 28 (min. 14 hrs/credit × 2 credits)
- **Budget**: ₹18,000 (₹3,000 × 6)

---

## 2. The Problem We Are Solving

### 2.1 Field Observations (Primary Data)
We conducted field visits to farming households near Roorkee and observed the following:

| # | Observation | Agronomic Consequence | Published Validation |
|---|---|---|---|
| 1 | Farmers apply fertilizer in fixed quantities passed down from previous generations — same type, same amount, regardless of soil status | Nutrient imbalance: Haridwar soils are **Low in N**, **High in P** (Pachauri et al. 2023, n=300), yet farmers keep applying DAP (which adds P) | Pachauri et al. 2023, Annals of Plant & Soil Res. |
| 2 | Farmers irrigate until water stands visibly across the entire field ("full flooding"), even for wheat and sugarcane which don't need submersion | Dissolved nitrate leaches below root zone → N lost to groundwater, not absorbed by crop | Krishan et al. 2016, NIH Roorkee, CWE 11(3):737–742 |
| 3 | Strict monoculture — only sugarcane OR wheat OR rice. No planned intercropping or rotation for soil health | Repeated nutrient extraction from same soil profile; no biological N-fixation from legumes | ICAR Kharif/Rabi Advisory 2024–25, Uttarakhand |
| 4 | No knowledge of which seed variety suits their soil/climate. Selection based on neighbour's advice or dealer suggestion | Mismatched variety × environment → sub-optimal yield even with correct fertilizer | KVK Dhanauri variety recommendations |
| 5 | No farmer possessed a Soil Health Card or was aware of the SHC scheme or district soil testing lab | Without soil test data, STCR-based dosing is impossible. Farmers operate blind | Verifiable on soilhealth.dac.gov.in |
| 6 | Older farmers resist change; younger generation is more receptive, especially when shown financial savings | Adoption must route through trusted intermediaries (KVK, Gram Pradhan), not direct outreach | — |

### 2.2 The "Nitrogen Paradox"
Urea is the cheapest, most subsidised fertilizer in India (₹266.50/45kg bag). Farmers throw bags of it on their fields. Yet soil tests consistently show **Haridwar is Low in Nitrogen**. Why?

Because excess Urea doesn't accumulate in soil. Nitrogen is highly mobile:
- Applied on **dry soil** → volatilises as ammonia gas (lost to air)
- Applied before **flooding/rain** → nitrate dissolves and leaches past root zone (lost to groundwater)
- The crop never absorbs it. The farmer's money literally evaporates or washes away.

**Our solution fixes the timing** — we tell the farmer exactly when to apply Urea relative to their canal water turn, so the water carries nutrients INTO the root zone, not PAST it.

---

## 3. Institutional Collaborations

### 3.1 Irrigation Department, Roorkee

| Detail | Value |
|---|---|
| **Contact level** | Chief Engineer (Level-2), via personal connection |
| **What they agreed to provide** | Canal rosters and Warabandi schedules for the Roorkee belt; historical canal delivery trends |
| **Data format expected** | Paper register photographs / scanned PDFs / Excel (to be digitised by us into JSON) |
| **Status** | Collaboration confirmed; data handover pending field visit |

### 3.2 Krishi Vigyan Kendra (KVK), Dhanauri, Haridwar

| Detail | Value |
|---|---|
| **Contact** | Head of KVK agreed to collaborate |
| **What they agreed to provide** | Regional soil data analysis, STCR ready reckoners for Haridwar crops, support during field soil testing visits |
| **Their mandate** | ICAR-mandated extension body. Responsible for interpreting SHC data and conducting Frontline Demonstrations (FLD) |
| **Address** | Dhanauri, Tehsil Roorkee, by Upper Ganga Canal, Old Roorkee Road (~12 km from Roorkee) |

### 3.3 Chief Agricultural Officer (CAO), Haridwar

| Detail | Value |
|---|---|
| **What we are requesting** | Block-wise Soil Health Card data (aggregated N, P, K, OC, pH values) for Haridwar district — as CSV/Excel or printed summaries |
| **Why the CAO** | The State Agriculture Department (under the CAO) runs the SHC scheme — they collect samples, test them, print cards. The CAO holds the district-level master data |
| **Status** | Meeting scheduled; data not yet received |
| **Fallback** | soilhealth.dac.gov.in Nutrient Dashboard provides district/block-level aggregated data publicly |

---

## 4. Verified Official Data & Recommendations

### 4.1 Haridwar District Soil Nutrient Status
*(Source: Pachauri et al. 2023, 300 samples across 6 blocks; validated by SHC portal dashboard)*

| Nutrient | Status | Implication |
|---|---|---|
| Available Nitrogen (N) | **Low** | Farmers must apply N, but timing is critical to prevent leaching |
| Available Phosphorus (P) | **High** | Most fields do NOT need additional P. Applying DAP is wasted money |
| Available Potassium (K) | **Medium** | Moderate K application needed |
| Sulphur (S) | **Medium** | Often neglected by farmers |

### 4.2 ICAR Official Fertilizer Recommendations

#### Wheat (Irrigated, Timely Sown) — Indo-Gangetic Plains / Uttarakhand
*(Source: ICAR-IIWBR; Vikaspedia; ICAR Rabi Advisory 2024–25)*

| Parameter | Value |
|---|---|
| **Recommended N:P₂O₅:K₂O** | **150 : 60 : 40 kg/ha** |
| **Basal dose** | Full P + Full K + 1/3 N at sowing |
| **1st top-dress** | 1/3 N at Crown Root Initiation (CRI) stage — ~21 days after sowing |
| **2nd top-dress** | 1/3 N at tillering/jointing — ~45 days after sowing |
| **FYM supplement** | 10 tonnes/ha before sowing |

#### Sugarcane (Sub-tropical) — Indo-Gangetic Plains
*(Source: ICAR Agro-Advisory; KVK extension literature)*

| Parameter | Value |
|---|---|
| **Recommended N:P₂O₅:K₂O** | **150–180 : 60–80 : 60 kg/ha** |
| **Basal dose** | Full P + Full K + 1/4 N at planting (in furrows) |
| **Split N application** | Remaining 3/4 N in 2–3 splits during tillering and earthing-up (45–90 DAP) |
| **Intercrop advisory** | Plant Moong/Urad between rows → fixes 40–60 kg N/ha biologically |
| **Irrigation advisory** | Limit to 15,000–18,000 L/bigha per event |

### 4.3 The STCR Targeted Yield Equation
*(Source: ICAR-IISS Bhopal, AICRP-STCR)*

$$FN_i = \frac{NR_i}{CF_i/100} \times T - \frac{CS_i}{CF_i} \times STV_i$$

**Unit clarification:** CS and CF in this document are percentage numbers, e.g. `50`, not fractions such as `0.5`. Hence the nutrient-requirement term divides by `CF/100`. A coefficient profile must declare the soil-test nutrient basis; fertilizer output is N, P₂O₅ and K₂O in kg/ha.

| Symbol | Meaning | Source |
|---|---|---|
| $FN_i$ | Fertilizer nutrient $i$ required (kg/ha) | Calculated |
| $T$ | Target yield (quintals/ha) | Farmer's choice or district average |
| $NR_i$ | Nutrient requirement per quintal of grain (kg) | ICAR field trial data (crop-specific) |
| $CS_i$ | % contribution of nutrient from soil | ICAR STCR coefficients (soil-type specific) |
| $CF_i$ | % contribution of nutrient from fertilizer | ICAR STCR coefficients |
| $STV_i$ | Soil Test Value — lab reading (kg/ha) | From SHC card or CAO data |

---

## 5. System Architecture

### 5.1 High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERFACES                          │
│                                                                 │
│   ┌──────────────────┐          ┌──────────────────────────┐    │
│   │  Flask Web App   │          │  WhatsApp Bot            │    │
│   │  (Browser-based) │          │  (Twilio/Meta Cloud API) │    │
│   │  Trilingual UI   │          │  Hindi text interface    │    │
│   └────────┬─────────┘          └────────────┬─────────────┘    │
│            │                                  │                  │
│            ▼                                  ▼                  │
│   ┌────────────────────────────────────────────────────────┐    │
│   │              Flask Backend (Python)                     │    │
│   │                                                        │    │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │    │
│   │  │ STCR Engine  │  │ Timing Engine│  │ Budget Engine │ │    │
│   │  │ (Fertilizer  │  │ (Leaching    │  │ (Integer LP  │ │    │
│   │  │  Dose Calc)  │  │  Risk Model) │  │  Optimizer)  │ │    │
│   │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │    │
│   │         │                 │                  │          │    │
│   │         ▼                 ▼                  ▼          │    │
│   │  ┌─────────────────────────────────────────────────┐   │    │
│   │  │          Recommendation Generator               │   │    │
│   │  │  → Shopping List (bags + ₹)                     │   │    │
│   │  │  → Application Calendar (dates + times)         │   │    │
│   │  │  → Savings Comparison (current vs. optimised)   │   │    │
│   │  │  → Printable PDF (Hindi advisory card)          │   │    │
│   │  └─────────────────────────────────────────────────┘   │    │
│   └────────────────────────────────────────────────────────┘    │
│                                                                 │
│   ┌────────────────────────────────────────────────────────┐    │
│   │                  DATA LAYER                            │    │
│   │                                                        │    │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │    │
│   │  │ Warabandi DB │  │ Weather API  │  │ SHC Data     │ │    │
│   │  │ (JSON files) │  │ (Open-Meteo) │  │ (CAO CSV +   │ │    │
│   │  │ From Irrig.  │  │ Free, no key │  │  Portal API) │ │    │
│   │  │ Dept data    │  │ 7-day daily  │  │              │ │    │
│   │  └──────────────┘  └──────────────┘  └──────────────┘ │    │
│   │                                                        │    │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │    │
│   │  │ STCR Coeffs  │  │ Fertilizer   │  │ Crop Stage   │ │    │
│   │  │ (ICAR/KVK    │  │ Price Table  │  │ Calendar     │ │    │
│   │  │  published)  │  │ (Govt-fixed) │  │ (ICAR std)   │ │    │
│   │  └──────────────┘  └──────────────┘  └──────────────┘ │    │
│   └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Backend** | Python 3.11 + Flask | Lightweight, easy to learn, huge ecosystem for scientific computing |
| **Frontend** | Jinja2 templates + Vanilla CSS | Government/institutional look; no JS framework overhead |
| **Multilingual** | Flask-Babel (i18n) | Supports Hindi + English + Garhwali labels; standard `.po` translation files |
| **Fonts** | Noto Sans Devanagari (Google Fonts) | Clean rendering of Hindi/Devanagari text on all devices |
| **Optimisation** | PuLP (Integer Linear Programming) | Converts continuous STCR doses to whole-bag purchases under budget constraint |
| **Weather API** | Open-Meteo (free, no API key, no credit card) | 7-day daily forecasts by lat/long; ECMWF/GFS data; completely free for non-commercial use |
| **WhatsApp Bot** | Meta WhatsApp Cloud API (production) + Twilio Sandbox (dev only) | Meta: dedicated +91 number, 1,000 free conversations/month, no join codes. Twilio: internal team testing only |
| **PDF Generation** | ReportLab or WeasyPrint | Generates printable Hindi advisory card (1-page PDF) for field distribution |
| **Scheduler** | APScheduler (Python) | Daily 7 AM weather alert cron job for opted-in farmers |
| **Database** | SQLite (local) / PostgreSQL (deployed) | Lightweight for prototype; stores Warabandi schedules, SHC data, bot sessions |
| **Deployment** | Render.com (paid starter, ~₹500/month) + local Flask dev server | No cold-start delay for WhatsApp webhook; online URL for committee demo |

### 5.3 Project Directory Structure

```
jal-khadd/
├── app.py                          # Flask entry point
├── config.py                       # Environment variables, API tokens
├── requirements.txt                # pip dependencies
├── .env                            # Secrets (NEVER committed to Git)
│
├── engine/                         # Core optimisation logic (shared by web + bot)
│   ├── __init__.py
│   ├── stcr.py                     # STCR targeted yield equation
│   ├── optimizer.py                # PuLP integer LP bag optimisation
│   ├── timing.py                   # Leaching risk + Warabandi sync
│   └── weather.py                  # Open-Meteo API integration
│
├── bot/                            # WhatsApp bot module
│   ├── __init__.py
│   ├── webhook.py                  # Flask blueprint: /webhook/whatsapp
│   ├── session.py                  # Session manager (SQLite-backed, per phone #)
│   ├── state_machine.py            # FSM: START→BLOCK→CROP→BUDGET→SOIL→RESULT
│   ├── parser.py                   # Hindi/Hinglish input parsing + synonym dict
│   ├── formatter.py                # Format optimiser output as Hindi WhatsApp text
│   ├── alerts.py                   # APScheduler cron: daily weather push alerts
│   └── meta_api.py                 # Meta Cloud API: send_text, send_document, send_image
│
├── routes/                         # Web app routes
│   ├── __init__.py
│   ├── advisory.py                 # Input form + results dashboard
│   ├── simulator.py                # Intercropping rotation simulator
│   └── pdf.py                      # PDF advisory card generator (ReportLab)
│
├── templates/                      # Jinja2 HTML templates
│   ├── base.html
│   ├── index.html
│   ├── advisory_form.html
│   ├── results.html
│   └── about.html
│
├── static/
│   ├── css/style.css               # Government/institutional theme
│   ├── fonts/                      # Noto Sans Devanagari
│   ├── images/
│   └── pdfs/                       # Generated advisory PDFs (served for WhatsApp media)
│
├── data/                           # Pre-loaded reference data
│   ├── warabandi.json              # Digitised canal schedules
│   ├── soil_averages.json          # Block-level SHC averages from CAO
│   ├── stcr_coefficients.json      # ICAR STCR parameters by crop
│   ├── fertilizer_catalog.json     # Products, nutrient %, govt MRP
│   └── crop_synonyms.json          # Hindi/Hinglish/English keyword maps
│
├── translations/                   # Flask-Babel i18n
│   ├── hi/LC_MESSAGES/messages.po  # Hindi translations
│   └── en/LC_MESSAGES/messages.po  # English (default)
│
├── tests/                          # Unit tests
│   ├── test_stcr.py
│   ├── test_optimizer.py
│   ├── test_parser.py
│   └── test_state_machine.py
│
└── jalkhadd.db                     # SQLite database (auto-created on first run)
```


## 6. Database Schema

### 6.1 Core Tables

```sql
-- Village-level Warabandi data (digitised from Irrigation Dept)
CREATE TABLE warabandi (
    id              INTEGER PRIMARY KEY,
    village_name    TEXT NOT NULL,
    block_name      TEXT NOT NULL,       -- e.g., Roorkee, Bhagwanpur, Laksar
    canal_name      TEXT,                -- e.g., Upper Ganga Canal, Branch X
    outlet_number   TEXT,
    day_of_week     TEXT NOT NULL,        -- e.g., "Wednesday"
    start_time      TEXT NOT NULL,        -- e.g., "08:00"
    duration_hours  REAL NOT NULL,        -- e.g., 4.5
    season          TEXT NOT NULL,        -- "Rabi" or "Kharif"
    source          TEXT DEFAULT 'Irrigation Dept Roorkee'
);

-- Soil Health Card data (from CAO Haridwar or SHC portal)
CREATE TABLE soil_data (
    id              INTEGER PRIMARY KEY,
    village_name    TEXT NOT NULL,
    block_name      TEXT NOT NULL,
    sample_year     INTEGER,
    nitrogen_status TEXT,                 -- "Low" / "Medium" / "High"
    nitrogen_kgha   REAL,                -- Actual value in kg/ha if available
    phosphorus_status TEXT,
    phosphorus_kgha REAL,
    potassium_status TEXT,
    potassium_kgha  REAL,
    organic_carbon  REAL,                -- %
    ph              REAL,
    sulphur_kgha    REAL,
    source          TEXT                 -- "CAO Haridwar" or "SHC Portal" or "Field Sample"
);

-- ICAR STCR Coefficients (from AICRP-STCR publications + KVK)
CREATE TABLE stcr_coefficients (
    id              INTEGER PRIMARY KEY,
    crop            TEXT NOT NULL,        -- "Wheat", "Sugarcane", "Rice"
    nutrient        TEXT NOT NULL,        -- "N", "P2O5", "K2O"
    nr_per_quintal  REAL NOT NULL,        -- NR: nutrient requirement per quintal yield
    cs_percent      REAL NOT NULL,        -- CS: % contribution from soil
    cf_percent      REAL NOT NULL,        -- CF: % contribution from fertilizer
    region          TEXT DEFAULT 'Indo-Gangetic Alluvial',
    source          TEXT                 -- "ICAR-IISS Bhopal" / "KVK Dhanauri"
);

-- Fertilizer product catalog (govt-fixed MRP)
CREATE TABLE fertilizers (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,        -- "Urea", "DAP", "MOP", "SSP"
    bag_weight_kg   REAL NOT NULL,        -- 45, 50, etc.
    n_percent       REAL DEFAULT 0,       -- Urea = 46%
    p2o5_percent    REAL DEFAULT 0,       -- DAP = 46%
    k2o_percent     REAL DEFAULT 0,       -- MOP = 60%
    mrp_per_bag     REAL NOT NULL,        -- ₹266.50 for Urea
    subsidised      BOOLEAN DEFAULT TRUE
);

-- User sessions / recommendation history
CREATE TABLE recommendations (
    id              INTEGER PRIMARY KEY,
    timestamp       TEXT NOT NULL,
    village_name    TEXT,
    crop            TEXT,
    sowing_date     TEXT,
    budget_rs       REAL,
    soil_n          REAL,
    soil_p          REAL,
    soil_k          REAL,
    recommended_bags TEXT,               -- JSON: {"Urea": 2, "DAP": 1}
    schedule_json   TEXT,                -- JSON: application calendar
    savings_rs      REAL,
    source          TEXT                 -- "web" or "whatsapp"
);
```

---

## 7. The Optimisation Algorithm (Pseudocode)

### 7.1 Step 1: STCR Dose Calculation (Continuous)

```
INPUT: crop, target_yield_T, soil_test_values (N, P, K)
LOAD:  stcr_coefficients for (crop, region)

FOR each nutrient i IN [N, P2O5, K2O]:
    FN_i = (NR_i / (CF_i / 100)) * T  -  (CS_i / CF_i) * STV_i
    FN_i = max(FN_i, 0)   // Cannot apply negative fertilizer

OUTPUT: required_kg = {N: FN_N, P2O5: FN_P, K2O: FN_K}
```

### 7.2 Step 2: Integer Bag Optimisation Under Budget Constraint

```
INPUT: required_kg (from Step 1), budget_B, fertilizer_catalog
OBJECTIVE: Maximise yield contribution (Liebig's Law)

DECISION VARIABLES:
    bags_j = integer number of bags of fertilizer j to buy (j ∈ {Urea, DAP, MOP, SSP})

CONSTRAINTS:
    Σ (bags_j × price_j)  ≤  B                    // Budget constraint
    bags_j ≥ 0                                      // Non-negativity
    bags_j ∈ integers                               // Whole bags only

OBJECTIVE FUNCTION:
    // Liebig's Law: yield is limited by the MOST DEFICIENT nutrient
    // Maximise the minimum nutrient satisfaction ratio

    FOR each nutrient i:
        supplied_i = Σ (bags_j × weight_j × nutrient_percent_ij)
        ratio_i = supplied_i / required_kg_i

    MAXIMISE  min(ratio_N, ratio_P, ratio_K)

SOLVER: PuLP (CBC solver, open-source)

OUTPUT: shopping_list = {Urea: 2 bags, DAP: 1 bag, MOP: 0 bags}
         total_cost = ₹1,883
```

### 7.3 Step 3: Application Timing (Leaching Risk Model)

```
INPUT: 
    village_name → warabandi (next canal turn: day, time)
    village_lat_lon → weather_forecast (7-day rainfall)
    soil_texture (Sandy / Loamy / Clay)
    crop_stage_calendar (from sowing_date)

RULES:
    1. Basal dose (Full P + Full K + 1/3 N) → apply at sowing. No timing issue.
    
    2. For each subsequent N top-dress:
        a. Find next_canal_turn (T₀) from Warabandi
        b. Check weather: rain_mm in 48-hour window around T₀
        c. Compute application_window:
            IF soil = Sandy:   apply_at = T₀ - 6 to 12 hours
            IF soil = Loamy:   apply_at = T₀ - 12 to 24 hours
            IF soil = Clay:    apply_at = T₀ - 24 to 36 hours
        d. Leaching risk flag:
            IF rain_mm > 20mm within 48 hrs of application:
                FLAG "HIGH RISK — delay application by one canal cycle"
            ELSE:
                RECOMMEND apply_at window

OUTPUT: 
    application_calendar = [
        {dose: "1 bag Urea", date: "Tue 14 Oct, evening", 
         reason: "Canal water arrives Wed 8 AM. Sandy soil — apply 12 hrs before."},
        {dose: "1 bag Urea", date: "~8 Nov (25 days later at tillering)", 
         reason: "Check weather 2 days before. Same timing rule."}
    ]
```

---

## 8. Web App — Pages & Features

### 8.1 Page Map

| Page | Route | Description |
|---|---|---|
| **Home / Landing** | `/` | Project overview, language selector (EN / HI / Garhwali), "Get Started" button |
| **Input Form** | `/advisory` | Multi-step form: Village → Crop → Soil Data → Budget |
| **Results Dashboard** | `/results/<id>` | Shopping list, application calendar, savings comparison, soil health gauges |
| **Print Advisory** | `/results/<id>/pdf` | Generates downloadable 1-page Hindi PDF for field distribution |
| **Rotation Simulator** | `/simulator` | Side-by-side comparison: monoculture vs. intercropping financial projection |
| **About / Methodology** | `/about` | STCR explanation, data sources, team info, collaborator logos |

### 8.2 Input Form — Multi-Step Flow

```
Step 1: Location
    ├── Select Block (dropdown): Roorkee / Bhagwanpur / Laksar / Narsan / Bahadrabad / Khanpur
    ├── Select Village (dropdown, filtered by block)
    └── [Auto-fills: lat/lon for weather, Warabandi schedule if available]

Step 2: Crop & Season
    ├── Select Crop: Wheat / Sugarcane / Rice / Maize
    ├── Sowing Date (date picker)
    └── Soil Texture: Sandy / Sandy-Loam / Loam / Clay-Loam / Clay

Step 3: Soil Health Data
    ├── Option A: "I have my SHC values" → Manual entry fields for N, P, K, OC, pH
    ├── Option B: "Fetch from SHC portal" → Enter phone number → auto-fetch (if available)
    └── Option C: "I don't have a card" → Uses block-level average from CAO data
        └── Shows message: "Using average soil data for [Block]. Get your soil tested 
            at District Lab, Bahadrabad (01334-239034) for a more precise recommendation."

Step 4: Budget
    ├── Enter total fertilizer budget (₹)
    └── Shows current prices: Urea ₹266.50/bag, DAP ₹1,350/bag, MOP ₹870/bag
```

### 8.3 Results Dashboard — Output Screens

**Screen A: Shopping List**
```
┌─────────────────────────────────────────────────┐
│  🛒  FERTILIZER SHOPPING LIST                   │
│  Crop: Wheat | Village: Dhandera | Budget: ₹2,000│
│                                                  │
│  ┌─────────┬──────┬──────────┬─────────────────┐│
│  │ Product │ Bags │ Cost (₹) │ Nutrients (kg)  ││
│  ├─────────┼──────┼──────────┼─────────────────┤│
│  │ Urea    │  2   │   533    │ N: 41.4         ││
│  │ DAP     │  1   │ 1,350    │ N: 9, P₂O₅: 23 ││
│  │ MOP     │  0   │     0    │ —               ││
│  ├─────────┼──────┼──────────┼─────────────────┤│
│  │ TOTAL   │  3   │ ₹1,883   │ Within budget ✓ ││
│  └─────────┴──────┴──────────┴─────────────────┘│
│                                                  │
│  ⚠️ Your soil is HIGH in Phosphorus.             │
│     You do NOT need additional DAP next season.  │
└─────────────────────────────────────────────────┘
```

**Screen B: Application Calendar**
```
┌──────────────────────────────────────────────────────┐
│  📅  APPLICATION SCHEDULE                            │
│  Synced with: Upper Ganga Canal — Outlet #14         │
│                                                      │
│  1️⃣  AT SOWING (15 Oct)                             │
│      Apply: Full DAP (1 bag) + ⅓ Urea (15 kg)       │
│      Method: Mix in furrows before sowing             │
│                                                      │
│  2️⃣  FIRST TOP-DRESS (5 Nov, ~21 DAP)               │
│      Apply: ⅓ Urea (15 kg)                          │
│      🕐 Apply Tuesday evening (canal turn: Wed 8 AM) │
│      🌧️ Weather: No rain expected ✅                  │
│      💡 Your soil is Sandy-Loam — apply 12-18 hrs    │
│         before water for maximum root absorption      │
│                                                      │
│  3️⃣  SECOND TOP-DRESS (30 Nov, ~45 DAP)             │
│      Apply: remaining ⅓ Urea (15 kg)                │
│      🕐 Check weather 2 days before. Same canal rule. │
│      ⚠️ If heavy rain forecast: DELAY by one cycle   │
└──────────────────────────────────────────────────────┘
```

**Screen C: Savings Comparison**
```
┌────────────────────────────────────────────────────┐
│  📊  YOUR SAVINGS                                  │
│                                                    │
│           CURRENT PRACTICE    OPTIMISED (Jal-Khadd)│
│  Urea     4 bags (₹1,066)    2 bags (₹533)        │
│  DAP      2 bags (₹2,700)    1 bag  (₹1,350)      │
│  ─────────────────────────────────────────────     │
│  Total    ₹3,766              ₹1,883               │
│                                                    │
│  💰 YOU SAVE: ₹1,883 per hectare                   │
│  📈 Projected yield: same or +10-15% (STCR-based)  │
│  🌊 N-leaching reduced: ~25% (timing optimisation) │
│                                                    │
│  Sources: ICAR-STCR, Pachauri et al. 2023,        │
│  IIT Roorkee SWAT+ simulation (EGU26-19661)        │
└────────────────────────────────────────────────────┘
```

**Screen D: Soil Health Dashboard (Gauges)**
```
Visual gauge/meter for each nutrient showing Low/Medium/High with 
the farmer's value marked. Color-coded: Red (deficient) → Yellow → Green (adequate).
```

**Screen E: Printable PDF Advisory Card**
- 1-page A4 PDF in Hindi
- Contains: Shopping list, calendar, village name, date
- Designed for the KVK/Krishi Mitra to print and hand to the farmer in the field
- Uses Noto Sans Devanagari font

**Screen F: Intercropping / Rotation Simulator**
- Input: Current monoculture crop + area
- Output: Side-by-side financial ledger — Monoculture vs. Sugarcane + Moong intercrop
- Shows: Seed cost, fertilizer savings from biological N-fixation (40-60 kg N/ha), market value of moong harvest

---

## 9. WhatsApp Bot — Full Specification (Primary Product Feature)

> The WhatsApp bot is not an add-on. It IS the product. The web app is for KVK scientists and committee demos; the WhatsApp bot is what actually reaches the farmer in the field.

### 9.1 Why WhatsApp is the Only Viable Channel

| Factor | Reality |
|---|---|
| **Smartphone penetration in rural Haridwar** | ~70% of farming households have at least one Android smartphone (NSSO 77th Round) |
| **App they already use daily** | WhatsApp. Not Chrome. Not Play Store apps. WhatsApp. |
| **Installation barrier** | Zero. No download, no sign-up, no storage space needed. The farmer already has WhatsApp. |
| **Literacy barrier** | WhatsApp voice notes can be used in future versions. For now, numbered menu options (reply "1", "2") require minimal literacy |
| **Data cost** | WhatsApp messages consume negligible data (~1-2 KB/message). Even farmers with ₹49 Jio plans can use it |

### 9.2 Architecture — How the Bot Works

```
┌─────────────────────────────────────────────────────────────────────┐
│                     WHATSAPP BOT ARCHITECTURE                       │
│                                                                     │
│  FARMER'S PHONE                                                     │
│  ┌──────────────┐                                                   │
│  │  WhatsApp    │──── sends "1" ────┐                               │
│  │  (Hindi msg) │                    │                               │
│  └──────────────┘                    ▼                               │
│                              ┌──────────────┐                       │
│                              │  Twilio /    │                       │
│                              │  Meta Cloud  │                       │
│                              │  API Gateway │                       │
│                              └──────┬───────┘                       │
│                                     │ HTTP POST (webhook)           │
│                                     ▼                               │
│                              ┌──────────────────────────────┐       │
│                              │  Flask Backend               │       │
│                              │  /webhook/whatsapp           │       │
│                              │                              │       │
│                              │  ┌────────────────────────┐  │       │
│                              │  │  Session Manager       │  │       │
│                              │  │  (tracks conversation  │  │       │
│                              │  │   state per phone #)   │  │       │
│                              │  └──────────┬─────────────┘  │       │
│                              │             │                │       │
│                              │             ▼                │       │
│                              │  ┌────────────────────────┐  │       │
│                              │  │  State Machine         │  │       │
│                              │  │  (determines next      │  │       │
│                              │  │   question to ask)     │  │       │
│                              │  └──────────┬─────────────┘  │       │
│                              │             │                │       │
│                              │     ┌───────┴────────┐       │       │
│                              │     │ All inputs     │       │       │
│                              │     │ collected?     │       │       │
│                              │     └───┬────────┬───┘       │       │
│                              │      No │        │ Yes       │       │
│                              │         ▼        ▼           │       │
│                              │  Ask next    ┌────────────┐  │       │
│                              │  question    │ SAME       │  │       │
│                              │              │ Optimiser  │  │       │
│                              │              │ Engine     │  │       │
│                              │              │ (STCR +    │  │       │
│                              │              │  PuLP +    │  │       │
│                              │              │  Timing)   │  │       │
│                              │              └─────┬──────┘  │       │
│                              │                    │         │       │
│                              │                    ▼         │       │
│                              │  ┌──────────────────────┐    │       │
│                              │  │  Response Formatter  │    │       │
│                              │  │  (Hindi text +       │    │       │
│                              │  │   emoji formatting + │    │       │
│                              │  │   PDF attachment)    │    │       │
│                              │  └──────────┬───────────┘    │       │
│                              └─────────────┼────────────────┘       │
│                                            │                        │
│                                            ▼                        │
│                              ┌──────────────────────┐               │
│                              │  Twilio / Meta API   │               │
│                              │  sends reply back    │               │
│                              │  to farmer's phone   │               │
│                              └──────────────────────┘               │
└─────────────────────────────────────────────────────────────────────┘

KEY DESIGN PRINCIPLE: The bot uses the EXACT SAME optimisation engine as 
the web app. Zero code duplication. One engine, two interfaces.
```

### 9.3 Conversation State Machine

The bot tracks each farmer's conversation using their phone number as the session key. Each session progresses through a finite state machine:

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  START  │────▶│  BLOCK  │────▶│  CROP   │────▶│ BUDGET  │────▶│  SOIL   │
│ (greet) │     │ (select │     │ (select │     │ (enter  │     │ (have   │
│         │     │  block) │     │  crop)  │     │  ₹)     │     │  SHC?)  │
└─────────┘     └─────────┘     └─────────┘     └─────────┘     └────┬────┘
                                                                  ┌──┴──┐
                                                              Yes │     │ No
                                                                  ▼     ▼
                                                          ┌─────────┐ ┌─────────┐
                                                          │SOIL_DATA│ │USE_AVG  │
                                                          │(enter   │ │(use blk │
                                                          │ N,P,K)  │ │ average)│
                                                          └────┬────┘ └────┬────┘
                                                               │           │
                                                               ▼           ▼
                                                          ┌───────────────────┐
                                                          │    RESULT         │
                                                          │ (run optimiser,   │
                                                          │  send shopping    │
                                                          │  list + calendar) │
                                                          └────────┬──────────┘
                                                                   │
                                                                   ▼
                                                          ┌───────────────────┐
                                                          │   FOLLOW_UP       │
                                                          │ "PDF चाहिए?"      │
                                                          │ "मौसम अपडेट?"     │
                                                          │ "फिर से शुरू?"    │
                                                          └───────────────────┘
```

**Session storage**: Python dictionary keyed by phone number, stored in SQLite for persistence across server restarts.

```python
# Session schema
sessions = {
    "+919876543210": {
        "state": "CROP",  # Current state in the FSM
        "block": "Roorkee",  # Collected so far
        "crop": None,
        "budget": None,
        "soil_source": None,  # "card" or "average"
        "soil_n": None,
        "soil_p": None,
        "soil_k": None,
        "last_active": "2026-10-20T12:00:00",
        "language": "hi",
    }
}
```

**Session expiry**: If no message received for 30 minutes, session resets to START. This prevents stale half-completed conversations.

### 9.4 Complete Conversation Flows

#### Flow A: Happy Path — No SHC Card (Most Common)

```
FARMER sends: "hi" / "namaste" / "शुरू" / any text
───────────────────────────────────────────────────
BOT replies:
🌾 *जल-खाद* में आपका स्वागत है!
कृषि विज्ञान केंद्र, धानौरी के सहयोग से

अपना ब्लॉक चुनें (नंबर भेजें):
1️⃣ रुड़की
2️⃣ भगवानपुर
3️⃣ लक्सर
4️⃣ नरसन
5️⃣ बहादराबाद
6️⃣ खानपुर
───────────────────────────────────────────────────
FARMER sends: "1"
───────────────────────────────────────────────────
BOT replies:
📍 ब्लॉक: *रुड़की* ✅

फसल चुनें:
1️⃣ गेहूं (Wheat)
2️⃣ गन्ना (Sugarcane)
3️⃣ धान (Rice)
4️⃣ मक्का (Maize)
───────────────────────────────────────────────────
FARMER sends: "1"
───────────────────────────────────────────────────
BOT replies:
🌾 फसल: *गेहूं* ✅

आपका इस सीज़न खाद का कुल बजट कितना है?
(सिर्फ रुपये में लिखें, जैसे: 2000)

📌 संदर्भ: यूरिया = ₹266/बोरी, DAP = ₹1,350/बोरी
───────────────────────────────────────────────────
FARMER sends: "2000"
───────────────────────────────────────────────────
BOT replies:
💰 बजट: *₹2,000* ✅

क्या आपके पास *मिट्टी स्वास्थ्य कार्ड* (Soil Health Card) है?
1️⃣ हाँ — मेरे पास कार्ड है
2️⃣ नहीं — कार्ड नहीं है

(अगर नहीं है तो चिंता न करें — हम आपके ब्लॉक के
औसत मिट्टी डेटा का इस्तेमाल करेंगे)
───────────────────────────────────────────────────
FARMER sends: "2"
───────────────────────────────────────────────────
BOT replies:
⏳ आपकी सलाह तैयार हो रही है...

[2-3 second delay while optimiser runs]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛒 *खाद खरीदारी सूची*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 रुड़की | 🌾 गेहूं | 💰 बजट ₹2,000

• यूरिया: *2 बोरी* — ₹533
• DAP:    *1 बोरी* — ₹1,350
• MOP:    0 बोरी
─────────────────────
कुल खर्च: *₹1,883* ✅ (बजट में)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 *कब और कैसे डालें*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1️⃣ *बुवाई के समय (15 अक्टूबर)*
   पूरा DAP (1 बोरी) + ⅓ यूरिया (~15 kg)
   → कूंड़ में मिलाकर डालें

2️⃣ *पहली टॉप ड्रेसिंग (~5 नवम्बर)*
   ⅓ यूरिया (~15 kg)
   🕐 *मंगलवार शाम* को डालें
   💧 नहर का पानी: *बुधवार सुबह 8 बजे*
   ⚡ मिट्टी दोमट है → 12-18 घंटे पहले डालें
       ताकि पानी खाद को जड़ों तक पहुँचाए

3️⃣ *दूसरी टॉप ड्रेसिंग (~30 नवम्बर)*
   बाकी ⅓ यूरिया (~15 kg)
   🕐 2 दिन पहले मौसम देखें

🌧️ *मौसम*: इस हफ्ते बारिश की संभावना नहीं ✅

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 *बचत*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
आपकी मौजूदा प्रथा: ~₹3,766/हेक्टेयर
जल-खाद सलाह:       ₹1,883/हेक्टेयर
─────────────────────
🎯 *आप बचाएंगे: ~₹1,883/हेक्टेयर*
📈 उपज: समान या 10-15% अधिक (STCR आधारित)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
और क्या चाहिए?
1️⃣ 📄 PDF कार्ड भेजें (प्रिंट करने के लिए)
2️⃣ 🌧️ मौसम अलर्ट चालू करें
3️⃣ 🔄 दूसरी फसल के लिए फिर से शुरू करें
4️⃣ ℹ️ इस सलाह का वैज्ञानिक आधार जानें
```

#### Flow B: Farmer HAS an SHC Card

```
(After budget step...)
FARMER sends: "1" (हाँ — मेरे पास कार्ड है)
───────────────────────────────────────────────────
BOT replies:
बढ़िया! 👍 अपने कार्ड से ये 3 नंबर भेजें:

नाइट्रोजन (N): _____ kg/ha
फॉस्फोरस (P): _____ kg/ha
पोटैशियम (K): _____ kg/ha

इस फॉर्मेट में लिखें: N,P,K
उदाहरण: 180,45,220
───────────────────────────────────────────────────
FARMER sends: "180,45,220"
───────────────────────────────────────────────────
BOT replies:
✅ मिट्टी डेटा प्राप्त:
• नाइट्रोजन: 180 kg/ha (*कम* — ⚠️ ध्यान दें)
• फॉस्फोरस: 45 kg/ha (*ज़्यादा* — अतिरिक्त DAP ज़रूरी नहीं)
• पोटैशियम: 220 kg/ha (*मध्यम*)

⏳ आपकी व्यक्तिगत सलाह तैयार हो रही है...

[→ Same result format as Flow A, but with personalised doses]
```

#### Flow C: Error Handling — Invalid Input

```
(At block selection step...)
FARMER sends: "hello" / "7" / "wheat" / gibberish
───────────────────────────────────────────────────
BOT replies:
❌ कृपया 1 से 6 के बीच कोई नंबर भेजें।

अपना ब्लॉक चुनें:
1️⃣ रुड़की
2️⃣ भगवानपुर
... (repeats same menu)

───────────────────────────────────────────────────
(At budget step...)
FARMER sends: "two thousand" / "दो हज़ार"
───────────────────────────────────────────────────
BOT replies:
❌ कृपया सिर्फ अंकों में लिखें, जैसे: 2000

आपका इस सीज़न खाद का कुल बजट कितना है? (₹ में)
```

**Error handling rule**: After 3 consecutive invalid inputs at the same step, the bot sends a help message with an example and offers to restart.

#### Flow D: PDF Advisory Card Delivery

```
(After results shown...)
FARMER sends: "1" (PDF कार्ड भेजें)
───────────────────────────────────────────────────
BOT replies:
📄 आपका व्यक्तिगत खाद सलाह कार्ड तैयार है।
[Attached: jalkhadd_advisory_रुड़की_गेहूं_20Oct2026.pdf]

इसे प्रिंट करवाकर अपने पास रखें। 🖨️
अगर कोई सवाल हो तो KVK धानौरी से संपर्क करें:
📞 Dr. Vinod Kumar (कृषि वैज्ञानिक): 9410523909
```

The PDF is generated server-side by ReportLab/WeasyPrint, uploaded to a public URL (Render static files or S3), and sent as a media message via Twilio's `msg.media()` API.

#### Flow E: Proactive Weather Alerts (Opt-in)

```
(After results shown...)
FARMER sends: "2" (मौसम अलर्ट चालू करें)
───────────────────────────────────────────────────
BOT replies:
🌧️ मौसम अलर्ट *चालू* ✅
अगले 7 दिन आपको रोज़ सुबह 7 बजे मौसम अपडेट मिलेगा।
बंद करने के लिए "बंद" लिखें।

───────────────────────────────────────────────────
[Next morning at 7 AM — automated cron job sends:]
BOT → Farmer:
🌤️ *आज का मौसम — रुड़की*
• तापमान: 28°C / 16°C
• बारिश: कोई संभावना नहीं ✅
• हवा: 12 km/h

💡 *आज यूरिया डालने का सही दिन है*
   (नहर कल सुबह आएगी)

───────────────────────────────────────────────────
[If rain is detected:]
BOT → Farmer:
⚠️ *मौसम चेतावनी — रुड़की*
• 🌧️ कल 25mm बारिश की संभावना
• ❌ *आज यूरिया न डालें* — बारिश से बह जाएगा
• ✅ बारिश के बाद 1-2 दिन इंतज़ार करें
```

This is implemented via a scheduled cron job (Python `APScheduler` or system cron) that runs daily at 7 AM, checks weather for all opted-in phone numbers, and sends proactive Twilio messages.

### 9.5 Hindi Input Parsing Strategy

Farmers won't always type perfect numbers. The bot needs to handle:

| What farmer might type | How bot parses it |
|---|---|
| `1` | Direct integer → valid option |
| `गेहूं` / `gehun` / `wheat` | Keyword matching against a Hindi/Hinglish/English synonym dictionary |
| `दो हज़ार` / `do hazar` | Rejected — ask to type digits. (Hindi NLP number parsing is error-prone and not worth the risk for a prototype) |
| `2000 rupees` / `₹2000` / `2000rs` | Regex strips non-digit characters, extracts `2000` |
| `180, 45, 220` / `180/45/220` / `180 45 220` | Regex splits on comma, slash, or space to extract 3 numbers |
| `haan` / `ha` / `yes` / `हाँ` | Maps to boolean `True` |
| `nahi` / `no` / `नहीं` / `2` | Maps to boolean `False` |

```python
# Synonym dictionary for crop detection
CROP_SYNONYMS = {
    "wheat": ["wheat", "gehun", "गेहूं", "गेहुं", "gehu"],
    "sugarcane": ["sugarcane", "ganna", "गन्ना", "गन्ने", "cane"],
    "rice": ["rice", "dhan", "धान", "chawal", "paddy"],
    "maize": ["maize", "makka", "मक्का", "corn", "makki"],
}
```

### 9.6 Platform Comparison & Selection

| Feature | Twilio WhatsApp Sandbox | Meta WhatsApp Cloud API |
|---|---|---|
| **Cost** | ₹0 (free trial credits) | 1,000 free conversations/month; then ~₹0.12/conversation |
| **Setup time** | 10 minutes | 1-2 days (Meta Developer account + Business verification) |
| **Max test users** | ~5 pre-registered numbers | Unlimited (after verification) |
| **Approval needed** | No — instant sandbox access | No for testing; Yes (Business verification) for production |
| **Send media (PDF/images)** | ✅ Yes — `msg.media(url)` | ✅ Yes — upload media via API |
| **Proactive messages** | ✅ Yes (within sandbox session) | ✅ Yes (via approved message templates) |
| **Indian phone numbers** | ✅ Works with +91 numbers | ✅ Native support |
| **Webhook setup** | Paste ngrok URL in Twilio Console | Paste URL in Meta Developer Dashboard + GET verification handshake |
| **Best for** | Internal dev testing only (6 team members) | **Everything else — committee demo AND farmer deployment** |

> [!CAUTION]
> **Twilio Sandbox CANNOT be used with real farmers.** It requires the farmer to save a US phone number (+1 415 523 8886), type `join <code-word>`, and re-join every 72 hours when the session expires. No farmer will do this. Use Twilio Sandbox ONLY during internal development among your 6 team members.

**Corrected Strategy (2 Phases):**

1. **Phase 1 (Internal Development)**: Use Twilio Sandbox for rapid prototyping among team members. Free, instant, zero approvals. Good for debugging the webhook and state machine.

2. **Phase 2 (Committee Demo + Farmer Deployment)**: Switch to **Meta WhatsApp Cloud API directly** with a dedicated Indian SIM. This gives you a real Indian phone number (+91) that farmers can save and message naturally — no join codes, no US numbers, no expiry.

### 9.7 Production Setup — Meta WhatsApp Cloud API (The Real Deployment)

> [!IMPORTANT]
> You do NOT need a registered company, GST certificate, or business verification to start. Meta allows **Unverified Business Accounts** to operate with up to 250 business-initiated conversations/day and unlimited customer-initiated (inbound) conversations. For our scale (10-50 farmers), this is more than enough.

#### Step 1: Buy a Dedicated SIM Card
```
→ Buy a new prepaid Indian SIM (Jio or Airtel, ~₹200 with 1-year recharge)
→ CRITICAL: This SIM must NEVER be registered on the consumer WhatsApp 
   or WhatsApp Business mobile app. If it was previously used on WhatsApp, 
   go to Settings → Account → Delete Account BEFORE proceeding.
→ This number becomes your bot's permanent WhatsApp identity: 
   e.g., +91 98765 XXXXX
```

#### Step 2: Create Meta Developer App
```
→ Go to developers.facebook.com
→ Log in with any Facebook account (can be a team member's personal account)
→ Click "Create App" → Select "Other" → Select "Business" type
→ Name it: "Jal-Khadd Advisory Bot"
→ On the App Dashboard, find "WhatsApp" and click "Set Up"
→ Meta auto-creates a WhatsApp Business Account (WABA) for you
```

#### Step 3: Link the Indian SIM
```
→ In left nav: WhatsApp → API Setup → Step 5: "Add a phone number"
→ Display Name: "जल-खाद Jal-Khadd" 
→ Category: "Education" or "Agriculture"
→ Enter your +91 number → Receive OTP via SMS → Verify
→ Your number is now an official WhatsApp API endpoint!
```

#### Step 4: Generate a Permanent API Token
```
→ Go to business.facebook.com → Settings → Users → System Users
→ Click "Add" → Name: "bot-service" → Role: Admin
→ Click "Add Assets" → Select your bot app → Full Control
→ Click "Generate New Token" → Select permissions:
   • whatsapp_business_messaging
   • whatsapp_business_management
→ Set expiration: "Never"
→ Save this token in your backend .env file — NEVER commit to Git
```

#### Step 5: Configure Webhook
```
→ Deploy Flask app to Render.com (same app, just different webhook format)
→ In Meta Dashboard: WhatsApp → Configuration
→ Callback URL: https://jal-khadd.onrender.com/webhook/whatsapp
→ Verify Token: (your secret string, e.g., "jalkhadd_verify_2026")
→ Click "Verify and Save" — Meta sends a GET request, your Flask app echoes 
   the hub.challenge, and the webhook is live
→ Under Webhook Fields, click "Manage" → subscribe to "messages"
```

#### Step 6: Sending Replies (API Call)
```python
# Instead of Twilio's TwiML response, you send a POST to Meta's Graph API:

import requests


def send_whatsapp_reply(phone_number, message_text):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {PERMANENT_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,  # e.g., "919876543210"
        "type": "text",
        "text": {"body": message_text},
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.json()


# Sending a PDF:
def send_whatsapp_pdf(phone_number, pdf_url, caption):
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "document",
        "document": {"link": pdf_url, "caption": caption, "filename": "jalkhadd_advisory.pdf"},
    }
    # ... same POST request as above
```

#### Step 7: Create a Farmer-Friendly Entry Point
```
→ Generate a direct chat link: https://wa.me/919876XXXXX?text=Namaste
→ Convert this to a QR code (free: qr-code-generator.com)
→ Print QR code on:
   • Pamphlets distributed at KVK Dhanauri
   • A banner at the farmer demo event
   • Your project poster for committee presentation
→ Farmer scans QR → WhatsApp opens → pre-filled "Namaste" → bot activates
```

#### Payment Card for Meta Billing
```
→ Meta requires a payment method on file even for the free tier
→ Use an Indian credit card (HDFC/ICICI/Axis/SBI Visa/Mastercard)
→ In bank app: enable "International Transactions" and "Online Transactions"
→ Meta will NOT charge you if under 1,000 service conversations/month
→ If no credit card available: use Fi Money or Niyo Global debit card (both 
   support international online payments from India)
```

### 9.7.1 Internal Dev Setup — Twilio Sandbox (Use This First, Then Migrate)

For the first 1-2 weeks of development, before your Meta account is ready:

```bash
# Install
pip install flask twilio

# Twilio Console → Messaging → Try it out → WhatsApp Sandbox
# Join with code from your phone: send "join <code-word>" to +1 415 523 8886
# Set webhook URL to your ngrok tunnel:

# Terminal 1:
python app.py  # Flask on localhost:5000

# Terminal 2:
ngrok http 5000
# Copy https://xxxx.ngrok-free.app/webhook/whatsapp → paste in Twilio Console
```

**Migration from Twilio to Meta Cloud API** requires changing only the webhook handler — the state machine, optimizer, and Hindi formatter code remain identical. The main difference is:
- Twilio sends `request.form['Body']` and expects TwiML XML response
- Meta sends `request.json` (nested JSON) and expects a separate POST call to reply

### 9.8 Webhook Code Structure

```python
# routes/whatsapp.py — the core webhook handler

from flask import Blueprint, request
from twilio.twiml.messaging_response import MessagingResponse
from engine.optimizer import run_optimization
from engine.timing import get_application_schedule
from engine.weather import get_forecast
from bot.session import get_session, update_session, reset_session
from bot.formatter import format_result_hindi, format_error_hindi
from bot.parser import parse_input

whatsapp_bp = Blueprint("whatsapp", __name__)


@whatsapp_bp.route("/webhook/whatsapp", methods=["POST"])
def webhook():
    """Main webhook — receives every incoming WhatsApp message."""
    incoming_msg = request.form.get("Body", "").strip()
    sender = request.form.get("From", "")  # e.g., "whatsapp:+919876543210"
    phone = sender.replace("whatsapp:", "")

    # Get or create session for this phone number
    session = get_session(phone)

    # Create Twilio response object
    resp = MessagingResponse()
    msg = resp.message()

    # Route based on current state
    state = session["state"]

    if state == "START":
        msg.body(WELCOME_MESSAGE_HINDI)
        update_session(phone, state="BLOCK")

    elif state == "BLOCK":
        block = parse_input(incoming_msg, input_type="block")
        if block is None:
            msg.body(format_error_hindi("block"))
        else:
            update_session(phone, state="CROP", block=block)
            msg.body(CROP_SELECTION_HINDI.format(block=block))

    elif state == "CROP":
        crop = parse_input(incoming_msg, input_type="crop")
        if crop is None:
            msg.body(format_error_hindi("crop"))
        else:
            update_session(phone, state="BUDGET", crop=crop)
            msg.body(BUDGET_PROMPT_HINDI)

    elif state == "BUDGET":
        budget = parse_input(incoming_msg, input_type="budget")
        if budget is None:
            msg.body(format_error_hindi("budget"))
        else:
            update_session(phone, state="SOIL", budget=budget)
            msg.body(SOIL_CARD_PROMPT_HINDI)

    elif state == "SOIL":
        has_card = parse_input(incoming_msg, input_type="boolean")
        if has_card is True:
            update_session(phone, state="SOIL_DATA", soil_source="card")
            msg.body(SOIL_DATA_ENTRY_HINDI)
        elif has_card is False:
            update_session(phone, state="RESULT", soil_source="average")
            # Run the optimizer immediately
            result = run_full_pipeline(session, phone)
            msg.body(result["text"])
            if result.get("pdf_url"):
                msg.media(result["pdf_url"])
        else:
            msg.body(format_error_hindi("boolean"))

    elif state == "SOIL_DATA":
        npk = parse_input(incoming_msg, input_type="npk")
        if npk is None:
            msg.body(format_error_hindi("npk"))
        else:
            update_session(phone, state="RESULT", soil_n=npk[0], soil_p=npk[1], soil_k=npk[2])
            result = run_full_pipeline(session, phone)
            msg.body(result["text"])
            if result.get("pdf_url"):
                msg.media(result["pdf_url"])

    elif state == "RESULT":
        # Follow-up actions
        choice = parse_input(incoming_msg, input_type="followup")
        if choice == "pdf":
            pdf_url = generate_pdf_card(session)
            msg.body("📄 आपका सलाह कार्ड:")
            msg.media(pdf_url)
        elif choice == "weather":
            enable_weather_alerts(phone, session)
            msg.body("🌧️ मौसम अलर्ट चालू ✅\nरोज़ सुबह 7 बजे अपडेट मिलेगा।")
        elif choice == "restart":
            reset_session(phone)
            msg.body(WELCOME_MESSAGE_HINDI)
            update_session(phone, state="BLOCK")
        elif choice == "science":
            msg.body(SCIENCE_EXPLANATION_HINDI)

    return str(resp), 200, {"Content-Type": "application/xml"}


def run_full_pipeline(session, phone):
    """Runs STCR + PuLP + Timing engine and returns formatted Hindi result."""
    s = get_session(phone)

    # Get soil data (from card or block average)
    if s["soil_source"] == "card":
        soil = {"N": s["soil_n"], "P": s["soil_p"], "K": s["soil_k"]}
    else:
        soil = get_block_average(s["block"])

    # Run STCR + Integer LP optimiser
    bags = run_optimization(crop=s["crop"], soil=soil, budget=s["budget"])

    # Get weather + warabandi + timing
    schedule = get_application_schedule(
        village=s.get("village") or s["block"], crop=s["crop"], bags=bags
    )

    # Format as Hindi WhatsApp message
    text = format_result_hindi(bags, schedule, s)

    # Log recommendation to database
    log_recommendation(phone, s, bags, schedule)

    update_session(phone, state="RESULT")
    return {"text": text, "pdf_url": None}
```

### 9.9 Media Capabilities

| Media Type | Use Case | How It's Sent |
|---|---|---|
| **PDF attachment** | Printable advisory card in Hindi (1-page A4) | Generated by ReportLab → saved to `/static/pdfs/` → sent via `msg.media(url)` |
| **Image** | Soil health gauge chart (optional, for visual learners) | Generated by Matplotlib → saved as PNG → sent via `msg.media(url)` |
| **Text with emoji** | Primary advisory output (shopping list + calendar) | Formatted Hindi string with Unicode emojis |

**PDF card content** (same as web app Screen E):
- Farmer's village + crop + date
- Shopping list table (product, bags, cost)
- Application calendar with dates
- Savings estimate
- KVK contact info
- "Powered by IIT Roorkee × KVK Dhanauri" footer

### 9.10 Cost Analysis (WhatsApp Bot Only)

| Item | Cost (₹) | Notes |
|---|---|---|
| Dedicated SIM card (Jio/Airtel prepaid, 1-year recharge) | ₹1,800 | One-time. Becomes the bot's permanent +91 number |
| Meta WhatsApp Cloud API — Service messages (inbound) | ₹0 | First 1,000 free/month. Our scale: 50-200 msgs/month |
| Meta WhatsApp Cloud API — Utility messages (weather alerts) | ~₹0.12/msg | ~₹180/month if 50 farmers opt in for daily alerts |
| Render.com paid tier (no cold-start delay, 24/7 uptime) | ~₹500/month | Free tier sleeps after 15 min inactivity → farmer waits 30s for first reply. Worth paying for demo reliability |
| **Total WhatsApp bot cost for 6 months** | **~₹5,000** | Well within the ₹18,000 budget |

**Breakdown of 1,000 free conversations/month:**
- Each time a farmer texts the bot and gets a reply within 24 hours = 1 "service conversation"
- A farmer using the bot once per week = 4 conversations/month
- 50 farmers × 4 uses/month = 200 conversations/month → **well under 1,000 free limit**
- Weather alerts (business-initiated utility messages) are billed separately at ₹0.12 each, but still negligible

### 9.11 Committee Defense — WhatsApp-Specific Questions

**Q: "Why WhatsApp and not a regular Android app?"**
> "Because our field visits showed that no farmer will download and install a new app. They don't have storage space, they don't trust unknown apps, and they don't visit the Play Store. But 100% of the smartphone-owning farmers we met use WhatsApp daily. By meeting them where they already are, we eliminate the entire adoption barrier. The bot requires zero downloads, zero sign-ups, and zero learning curve — they just send a message."

**Q: "Is the WhatsApp bot just a gimmick wrapper over the web app?"**
> "No. The WhatsApp bot has a unique capability the web app cannot replicate: *proactive weather alerts*. Once a farmer opts in, the bot pushes daily weather-synced fertilizer timing advice directly to their phone at 7 AM — including leaching risk warnings on rain days. The web app requires the farmer to actively visit a URL; the WhatsApp bot actively reaches out to the farmer. This push vs. pull difference is the core innovation."

**Q: "How do you handle farmers who can't read Hindi text well?"**
> "The bot uses numbered menus (reply 1, 2, 3) which require minimal literacy — just single-digit number recognition. The output uses emojis as visual anchors (🛒 for shopping, 📅 for calendar, 💰 for money, 🌧️ for weather) so even a semi-literate farmer can parse the structure. In a future version, we plan to add voice note support using speech-to-text, but for the MVP, numbered menus are sufficient and battle-tested by government bots like MyGov."

**Q: "What about data privacy? You're storing farmers' phone numbers."**
> "We store only the phone number (as session key), block name, crop, and soil values. No Aadhaar, no bank details, no personal identity data. The session auto-expires after 30 minutes. Recommendation history is anonymised in the database (phone number hashed). This is less data than a farmer gives when they walk into a fertilizer shop."

**Q: "What happens if Meta changes their pricing or shuts down the API?"**
> "Two things: (1) WhatsApp Business API has been stable since 2018 — Meta is investing more, not less, in it. (2) Our architecture is modular — the optimisation engine, state machine, and Hindi formatter are all backend Python code that doesn't depend on WhatsApp. If we ever needed to switch to Telegram, SMS, or IVRS, we only change the webhook transport layer. The brain of the system stays intact."

**Q: "Can this actually scale beyond your 50-farmer pilot?"**
> "Yes. The Meta Cloud API is built for enterprise scale — it handles millions of messages per day for companies like JioMart and Flipkart. Our architecture (stateless webhook + database-backed sessions + shared optimisation engine) has no single-farmer bottleneck. To scale to 10,000 farmers across Uttarakhand, we'd need: (1) complete Meta Business Verification (~1 week), (2) PostgreSQL instead of SQLite, (3) a ₹500/month server upgrade. Total additional cost: ~₹6,000/year."

### 9.12 Future Enhancement — Voice Note Support (Project Bhashini)

> This is NOT in the MVP. This is a documented future roadmap item for committee discussion.

Many farmers prefer sending **WhatsApp voice notes** over typing. The pipeline to support this:

```
Farmer sends 30-second voice note in Hindi/Garhwali
         │
         ▼
Meta Cloud API delivers .ogg audio file URL in webhook POST
         │
         ▼
Flask backend downloads .ogg file
         │
         ▼
Bhashini API (bhashini.gov.in) — Government of India's FREE 
Hindi speech-to-text service for Indian developers
         │
         ▼
Transcribed Hindi text → fed into the same state machine
         │
         ▼
Bot replies with text (same format as always)
```

**Why Bhashini?**
- **Free** for Indian academic/research use — government initiative under Digital India
- Supports **22 Indian languages** including Hindi, Garhwali (via Hindi model), Bhojpuri
- Specifically designed for Indian accents and dialects (trained on Indian voice data)
- No OpenAI/Google API costs needed

**Implementation effort**: ~1 day of coding (download audio → POST to Bhashini endpoint → parse transcript → feed to state machine). Can be added as a Sprint 2 feature after the MVP is stable.

---

## 10. Deployment Plan

### 10.1 Online Deployment (Committee Demo)

| Service | Plan | Cost | URL |
|---|---|---|---|
| **Render.com** | Free tier (web service) | ₹0 | `https://jal-khadd.onrender.com` |
| **Alternative: PythonAnywhere** | Free tier | ₹0 | `https://jalkhadd.pythonanywhere.com` |
| **Database** | SQLite file bundled with app (free tier doesn't need Postgres) | ₹0 | — |

### 10.2 Local Demo (Backup)
```bash
git clone https://github.com/[your-repo]/jal-khadd.git
cd jal-khadd
pip install -r requirements.txt
python app.py
# Opens at http://localhost:5000
```

---

## 11. Multilingual Strategy (Trilingual)

| Language | Scope | Implementation |
|---|---|---|
| **Hindi (हिंदी)** | Primary interface language; all farmer-facing output | Flask-Babel `.po` files; Noto Sans Devanagari font |
| **English** | Technical labels, scientific terms, committee-facing pages | Default locale |
| **Garhwali (गढ़वाली)** | Key agricultural terms and tooltips only (e.g., local names for crops, soil types) | Supplementary glossary JSON; shown as tooltips/parentheticals |

Language switcher: dropdown in header bar. Persisted in session cookie.

---

## 12. Development Roadmap

### Phase 1: Foundation (Week 1–2)

| Task | Owner | Hours |
|---|---|---|
| Set up Flask project structure, virtual env, Git repo | Pair C | 3 |
| Design database schema, create SQLite tables, seed fertilizer catalog | Pair B | 2 |
| Digitise Warabandi data (from Irrigation Dept photos/PDFs → JSON/SQL) | Pair A | 3 |
| Input CAO/SHC soil data into database (once received) | Pair A | 2 |
| Implement STCR dose calculation function (Python) | Pair B | 3 |
| Set up Open-Meteo weather API integration | Pair A | 2 |

### Phase 2: Core Engine (Week 3–4)

| Task | Owner | Hours |
|---|---|---|
| Implement PuLP integer optimisation (bags + budget constraint) | Pair B | 4 |
| Implement leaching-risk timing model (water balance + rules) | Pair B | 3 |
| Build input form pages (Jinja2 templates, multi-step form) | Pair C | 4 |
| Build results dashboard (shopping list, calendar, savings) | Pair C | 4 |
| Implement Flask-Babel i18n (Hindi translations) | Pair C | 3 |

### Phase 3: WhatsApp + Polish (Week 5–6)

| Task | Owner | Hours |
|---|---|---|
| Set up Twilio WhatsApp sandbox; build webhook endpoint | Pair A | 4 |
| Implement WhatsApp conversation flow (Hindi) | Pair A | 3 |
| Build PDF advisory card generator (ReportLab) | Pair C | 3 |
| Build intercropping rotation simulator page | Pair B | 3 |
| Build soil health gauge/dashboard visualisation | Pair C | 2 |
| CSS styling — government/institutional theme | Pair C | 3 |

### Phase 4: Testing & Deployment (Week 7–8)

| Task | Owner | Hours |
|---|---|---|
| Deploy to Render.com; test online URL | Pair A | 2 |
| Field testing with 2-3 farmers (KVK-facilitated) | All | 4 |
| Collect farmer feedback; iterate on UI | All | 3 |
| Prepare committee presentation; record demo video | All | 3 |
| Write final project report | All | 4 |

---

## 13. Budget Allocation

| Item | Amount (₹) | Notes |
|---|---|---|
| Travel (KVK + Irrigation Dept + CAO + village visits × 3-4 trips) | 7,000 | Auto/bus fare from IIT Roorkee campus |
| Printed Hindi advisory cards (laminated, A4, 50 copies) | 2,000 | For field distribution during farmer demo |
| Farmer demo event (tea, snacks, banner, venue) | 3,000 | At village Panchayat Bhavan or KVK premises |
| Domain name (optional: jalkhadd.in) | 1,000 | 1-year `.in` domain |
| Twilio credits (if needed beyond free sandbox) | 1,000 | Likely not needed for prototype scale |
| Contingency | 4,000 | Unexpected printing, travel, or data costs |
| **TOTAL** | **₹18,000** | |

---

## 14. Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| CAO data delayed / not received | Medium | Medium | Use SHC portal dashboard aggregates + Pachauri et al. 300-sample dataset |
| Irrigation Dept doesn't provide Warabandi in time | Low | Medium | Reconstruct from farmer interviews (primary data, actually stronger for committee) |
| KVK scientist unavailable | Low | Low | Use ICAR published STCR coefficients (freely available) |
| Farmers don't cooperate for field testing | Low | Medium | Go through KVK or Gram Pradhan introduction; frame in economic terms (₹ saved) |
| Render.com free tier is slow for demo | Low | Low | Run local Flask server as backup during committee presentation |
| WhatsApp Bot approval takes too long (Meta verification) | Medium | Low | Use Twilio sandbox for demo (works with pre-registered numbers; explain to committee it's a prototype) |

---

## 15. References & Data Sources

1. Pachauri et al. 2023, *Annals of Plant & Soil Research* — Haridwar district soil nutrient status (300 samples, 6 blocks)
2. Krishan et al. 2016, *Current World Environment* 11(3):737–742 — Groundwater conditions, Haridwar (NIH Roorkee)
3. ICAR-IISS Bhopal — AICRP-STCR Targeted Yield Equations (published coefficients)
4. ICAR-IIWBR — Wheat fertilizer recommendations for Indo-Gangetic Plains
5. ICAR Kharif/Rabi Agro-Advisories 2024–25, Uttarakhand
6. IIT Roorkee, SWAT+ simulation, Hindon basin — EGU26-19661, 2026
7. CGWB Groundwater Brochure, Hardwar District
8. soilhealth.dac.gov.in — Nutrient Dashboard & Fertilizer Calculator
9. Open-Meteo API — open-meteo.com (free weather forecast, no API key required)
10. KVK Dhanauri — haridwar.kvk4.in (crop variety recommendations, extension literature)
