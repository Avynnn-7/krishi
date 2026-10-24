# Jal-Khadd

A runnable, bilingual research prototype implementing the supplied [technical specification](technical_specification.md): shared nutrient calculations, budgeted whole-bag optimization, irrigation-aware scheduling, a Flask website, and a Hindi WhatsApp conversation engine.

**Not a field-ready fertilizer prescription.** Official local STCR coefficients, numeric soil averages and canal rosters were not supplied. They are not fabricated. Every report identifies its assumptions and requires agronomist review.

## Run locally

Python 3.11+ is required. The implementation was tested locally with Python 3.14.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
pybabel compile -d translations
python -m flask --app app:create_app run --host 127.0.0.1 --port 5050
```

Open **http://127.0.0.1:5050**. The Hindi assistant is at `/bot`.

The web app, optimizer, bot simulator and exports work without external credentials. CBC ships with the declared PuLP 3.x package. A missing/non-optimal solver produces an explicit error, not a substitute shopping list.

The SQLite database and a persistent local signing key are created in the ignored `instance/` directory. Reports survive server restarts. Do not delete that directory to reset the application. Use report deletion or the retention command instead.

`python app.py` also starts the app on port 5000. Debug mode is off.

## Practical features for farmers and extension workers

| Feature | Where | What it answers |
| --- | --- | --- |
| **Personal action plan** | Top of every report, PDF and bot reply | “What should *I* change first?” — prioritised, bilingual actions with reasons and field quantities (soil, money, timing, water). |
| **Soil Health Card interpretation** | `/soil-card` and every report | N, P, K, OC, pH, EC, S, Zn, Fe, Mn, Cu, B rated with gauges, plain-language meaning, and amendment quantities (zinc sulphate, gypsum, borax) for your field. Flags likely unit mistakes (ppm vs kg/ha, P vs P₂O₅). |
| **Personalised dose** | Fertilizer plan | With a card, the general dose is scaled 125/100/75% by soil-test rating; FYM/compost credit is subtracted; dealer prices and out-of-stock products are respected. |
| **Habit check** | Report “current practice” table | Compares the bags you usually buy with what the field needs — exposes the DAP habit and missing potash/nitrogen, with cost difference. |
| **Exact irrigation water** | `/water` and every report | Number of irrigations, date and crop stage, **depth (cm)**, **litres per bigha/acre**, **m³ for the field**, **pump hours**, how deep the soil should get wet, and whether your canal turn is long enough. |
| **Irrigation method comparison** | Water plan | Wild flooding, kiyari/borders, laser levelling, furrows, raised beds, sprinkler, drip, rice CF vs AWD — season water, savings %, pump hours, **advantages and disadvantages** in Hindi and English. |
| **Limited water mode** | “Irrigations you can get” | Schedules only the most yield-critical stages (e.g. wheat: CRI → flowering → milk → jointing). |
| **Field practicalities** | Form | Bigha presets (Uttarakhand ~632 m², kachha, pucca), drum/bucket flow measurement, “use my location”, edit & recalculate any report. |

## Included

- Responsive English/Hindi web interface and progressively enhanced three-step form.
- Wheat and sugarcane reference doses from the specification; general Indo-Gangetic rice/maize doses (confirm with KVK).
- Soil-card interpretation (`engine/soil_card.py`, `data/soil_ratings.json`), soil-rating dose scaling and FYM credit.
- FAO-56 irrigation planner (`engine/irrigation.py`, `data/crop_water.json`, `data/climate_normals.json`) with method comparison, canal-turn check, limited-water mode and forecast-based postponement.
- Personal recommendation engine (`engine/recommendations.py`) and current-practice comparison.
- Expanded editable fertilizer catalog (Urea, DAP, MOP, SSP, NPK 12:32:16, NPK 10:26:26) with per-plan dealer prices and availability.
- STCR implementation with percent normalization, soil nutrient basis conversion, profile provenance, crop/yield range validation and nonnegative doses.
- Hectare/acre conversion; bigha requires an explicit local square-metre conversion.
- PuLP integer whole-bag purchases within the exact paise budget.
- Separate **purchased**, **allocated for application**, **leftover**, and **unmet nutrient** quantities.
- Lexicographic objectives: minimum coverage, total coverage, minimum cost, minimum allocated mass. Coverage is capped at 100% and is **not yield**.
- Crop-stage schedules, all P/K at basal, compound-fertilizer N accounting, farmer-reported recurring irrigation, and explicit unknown/high rainfall risks.
- Optional Open-Meteo forecasts; timeouts, malformed data and missing dates remain unknown.
- Persisted reports, browser-scoped history, deletion, JSON output, RFC 5545 calendar export and one-page Hindi/English PDFs with shaped Devanagari.
- Sugarcane/moong economic comparison with editable prices, extra costs, crop-competition loss and break-even yield. N credit defaults to zero.
- Shared Hindi bot FSM with area, sowing date, texture, water turn, coordinates, budget, soil basis and lab input; Hindi/Hinglish crop parsing; session resumption, expiry and retry guidance.
- Signed Meta webhook and signed Twilio **internal sandbox** webhook, duplicate-message protection and persisted reply retry.
- Explicit alert opt-in/STOP/DELETE; separate 07:00 IST scheduler using approved Meta templates.
- Regression and integration tests; no tests contact Meta, Twilio or a real farmer.

## Important differences from the original roadmap

1. This is an optimization/rules model, **not a trained machine-learning model**. There is no training dataset in the supplied material.
2. The STCR formula is `NR*T/(CF/100) - CS*STV/CF` when CS/CF are entered as percentages. Using `NR/CF` directly would understate the crop requirement term 100-fold.
3. Without a reviewed STCR profile, entered soil readings scale the general dose by soil-test rating (125/100/75%); target yield is used only by STCR profiles. District "high P" is never applied to an individual field without its own test.
4. No invented block averages, official village coordinates, SHC phone-lookup service or canal schedules. Users explicitly supply their village, optional coordinates and water turn.
5. Bags bought are not automatically bags applied. Whole-bag surplus is shown separately; allocated nutrient masses cannot exceed the model requirements.
6. Heavy rain triggers HOLD/reassessment, not an automatically safe next canal cycle. Daily rainfall conservatively includes the application interval plus 24 hours each side. No universal litres/bigha prescription.
7. No claims of guaranteed yield improvement, quantified leaching reduction or savings versus an invented baseline. Enter a same-field baseline to compare **purchase costs**, not equivalent agronomic outcomes.
8. Garhwali translation, voice messages, verified seed-variety advice, official-data import tools, authenticated multi-user administration and PostgreSQL deployment are not implemented. Local language terms should be reviewed before offering them as Garhwali.
9. The prototype uses SQLite, synchronous inbound processing and a single scheduler. It is not advertised as a production-scale deployment.

## Configuration

Copy `.env.example` to `.env` and change only the services you want to enable. Never commit `.env`, databases, phone numbers, local keys or access tokens.

| Setting | Purpose |
| --- | --- |
| `SECRET_KEY` | Long random stable secret for Flask sessions and HMAC bot identities. Set explicitly for deployment. Rotating it invalidates sessions and changes bot identities. |
| `DATABASE_PATH` | SQLite file path; use persistent storage. Default is `instance/jalkhadd.db`. |
| `PUBLIC_BASE_URL` | Exact public HTTPS origin used in WhatsApp report/document links. |
| `WEATHER_ENABLED` | Defaults to `true`: 7-day rain at field coordinates or the block town (only coordinates are sent; cached 30 min). Set `false` for offline use. |
| `RATE_LIMIT_PER_MINUTE` | POST requests per client IP per minute (default 40; `0` disables). |
| `TRUST_PROXY` | Set `true` behind one trusted reverse proxy so rate limits use the real client IP. |
| `COOKIE_SECURE` | Set `true` behind HTTPS; leave `false` for local HTTP. |
| `META_VERIFY_TOKEN` | Secret used for webhook verification GET. |
| `META_APP_SECRET` | Verifies the `X-Hub-Signature-256` raw-body HMAC. |
| `META_ACCESS_TOKEN` / `META_PHONE_NUMBER_ID` | Your actual messaging credentials; not included. |
| `META_GRAPH_VERSION` | Configurable Graph API version; check provider support during setup. |
| `META_ALERT_TEMPLATE` / `META_ALERT_LANGUAGE` | Approved utility template name and language, normally `hi`. |
| `TWILIO_AUTH_TOKEN` | Validates sandbox request signatures. |
| `TWILIO_WEBHOOK_URL` | Exact externally configured HTTPS URL, including any query string. Do not derive signature validation from untrusted proxy headers. |

Only coordinates and public forecast parameters go to Open-Meteo. Names, budget and lab readings are not sent to the weather service. Weather snapshots in existing reports do not update automatically; create a fresh report or check a current forecast before application.

## WhatsApp setup

### Meta

1. Configure your own Meta business messaging number and credentials.
2. Set `PUBLIC_BASE_URL` to the reachable HTTPS origin, then configure `/webhook/whatsapp` as the callback.
3. Set the verification token and subscribe to messages.
4. Use valid Meta-signed requests. Unconfigured endpoints return 503; invalid signatures return 403.
5. Incoming text advances the same engine used by the web app. Unsupported media gets a clear text-only response.
6. Follow-up `1` sends a PDF document URL. Report URLs are capability/bearer links, so treat them as private.

There are **no embedded live tokens or external message sends in the local demo**. Current account eligibility, conversation windows, Graph versions and pricing must be checked with Meta; dated pricing in the specification is not a service guarantee.

The inbox stores one generated reply per provider message ID before transmission. A failed send returns 502; a retried webhook reuses the saved reply without re-running the FSM. A crash between provider acceptance and recording the successful send can still produce a duplicate delivery; this is not an exactly-once delivery guarantee.

### Twilio

Configure `/webhook/twilio` with the exact `TWILIO_WEBHOOK_URL`. The endpoint verifies `X-Twilio-Signature` and returns TwiML with text/document media. Use it only with internally enrolled sandbox numbers. Proactive Meta alert opt-in is disabled through the Twilio adapter.

### Local conversation example

At `/bot`, send the following one message at a time:

```text
नमस्ते
1
Dhandera
गेहूं
1
2026-11-01
3
नहीं
नहीं
2000
2
```

This selects Roorkee, wheat, one hectare, a specified sowing date, loam, no reported water turn/coordinates, a total INR 2,000 budget and no soil card. The result explicitly uses reference data rather than pretending to be STCR-calibrated. Use a season-appropriate date for a new demonstration.

### Weather alerts

An opted-in real Meta user must have supplied coordinates. Create an approved Hindi **utility template with exactly one body variable**, the predicted rain total in mm. Suggested content for review:

> अगले दो कैलेंडर दिनों में लगभग {{1}} mm बारिश का अनुमान है। खाद डालने से पहले रुकें और कृषि विशेषज्ञ/ताज़ा मौसम से फिर जाँच करें। यह शोध प्रोटोटाइप है। STOP भेजकर अलर्ट बंद करें।

Run **exactly one** dedicated process on the same persistent database:

```bash
flask --app app:create_app alerts --once  # explicit single sweep
flask --app app:create_app alerts         # daily at 07:00 Asia/Kolkata
```

Both commands fail explicitly if configuration is incomplete. The scheduler sends a warning only when today's plus tomorrow's daily rain total is **strictly greater than 20 mm**. Missing days are not considered dry. Successful warnings are limited to one per subscriber per local day; failed deliveries are logged and remain eligible for retry. The approved template must disclose that daily totals are a calendar-day approximation, not precise hourly predictions.

Do not start a scheduler in each Gunicorn worker, or multiple scheduler replicas. Two independent Render services cannot simply share the web service's local disk; use a single-host scheduled task for this prototype or redesign storage/dispatch before scaling.

## Reviewed STCR profiles

`data/stcr_coefficients.json` intentionally starts with an empty `profiles` array. Add **actual locally applicable, reviewed** entries, then restart the app. Each entry is validated as `engine.stcr.Profile`:

| Field | Meaning |
| --- | --- |
| `id` | Unique profile identifier. |
| `crop` | `wheat`, `sugarcane`, `rice` or `maize`. |
| `region` | Soil/region applicability description. |
| `source` | Actual publication/reckoner reference. |
| `verified_by` | Reviewer attribution. |
| `soil_basis` | `elemental` or `oxide`, matching coefficient calibration. |
| `min_yield`, `max_yield` | Validated target-yield range in quintals/ha. |
| `coefficients` | Exactly `N`, `P2O5`, `K2O`, each with `nr_per_quintal`, `cs_percent`, `cf_percent`. |

Profile nutrient keys describe fertilizer output. `soil_basis` describes the corresponding soil-test input used in the equation. Confirm soil extraction method and all published units before loading. A schema-valid profile is **not** independent verification of agronomic correctness; an operator can mislabel data.

Profiles appear in the web form and may be selected through the API. The simplified WhatsApp workflow intentionally remains reference-only until a local policy for selecting calibrated soil-specific profiles is established.

No placeholder numeric STCR profile is shipped. Synthetic coefficients exist only in tests.

## API

`GET /api/config` creates a browser session and returns its CSRF token. Use the same cookie jar and `X-CSRF-Token` for POST requests.

```json
{
  "block": "Roorkee",
  "village": "Dhandera",
  "crop": "wheat",
  "sowing_date": "2026-11-01",
  "area": 1,
  "area_unit": "ha",
  "budget": 2000,
  "texture": "loam"
}
```

Send this to `POST /api/advisory`. A successful 201 response contains `id`, `inputs`, `area_ha`, `method`, `warnings`, `plan`, `weather`, `schedule` and `cost_difference`. Validation failures return 422 with explicit errors. Monetary input accepts at most two decimal places. Lab values must be kg/ha, not ppm.

| Route | Result |
| --- | --- |
| `/results/<id>` | HTML report |
| `/results/<id>/json` | Full saved JSON |
| `/results/<id>/pdf?lang=hi` | Hindi A4 PDF |
| `/results/<id>/calendar.ics` | Tentative events with warnings |
| `/history` | Latest 20 reports from this browser |
| `/soil-card?N=..&P=..&K=..` | Soil Health Card interpretation (GET, shareable) |
| `/water?crop=..&sowing_date=..` | Irrigation calculator (GET, shareable) |
| `/village-soil` | Official Village Soil Data Hub + CSV/form importer for lab sheets |
| `/api/autofill` | One-call automatic resolution of GPS, block, village soil, live weather & water |
| `/api/geocode` | Resolve village name, GPS `(lat, lon)`, or Google Maps link to Haridwar block/village |
| `/api/voice-decipher` | Parse natural Hindi/Hinglish spoken sentences into structured field inputs |
| `/api/village-soil` | GET/POST official village soil records |
| `/advisory?from=<id>` | Edit and recalculate an existing report |
| `POST /results/<id>/delete` | Delete a report created by this browser |
| `POST /api/bot` | Local simulator message: `{"text":"नमस्ते"}` |
| `/health` | App/SQLite health |

## Privacy and operating limits

- Reports have random 192-bit bearer identifiers. **Anyone with a link can read a report.** This is not authenticated access control.
- Browser history is scoped to a signed session cookie; it is not a global list.
- Bot session identities use HMAC-SHA256, not reversible phone numbers. Raw phone numbers and coordinates are stored **only for explicitly opted-in alert subscriptions**. Protect the database and backups; it is not encrypted by the application.
- Conversation progress resets after 30 minutes of inactivity. Stored records are retained until deletion/purge; expiry is not a claim that all database bytes are erased.
- `STOP` removes alert consent. `DELETE` removes consent, the current stored bot session and reports still associated with it.
- Webhook receipt rows may retain prior replies until purge. A report's deletion makes old report links return 404. Provider-held messages and backups cannot be retracted by this application.
- Run retention deliberately:

```bash
flask --app app:create_app purge-data --days 30
```

This removes old report/session/receipt records but keeps alert subscriptions until STOP. Clearing browser cookies only clears its index, not the underlying data.

For a real rollout, add authenticated staff access, field-specific agronomic approval, access logging/redaction, rate limits, backed-up storage, provider delivery monitoring, an explicit retention policy and verified data. The prototype should not be exposed as an unattended public advisory service.

## Validation

```bash
python -m pytest -q
ruff check .
ruff format --check .
python -m compileall -q app.py storage.py exports.py engine bot
node --check static/js/app.js  # optional JS syntax check if Node is available
```

Tests cover soil-card boundaries and unit conversion, micronutrient amendments, rating-based dosing, FYM credit, dealer prices/availability, current-practice comparison, irrigation volume arithmetic, method ordering, AWD savings range, wheat CRI coverage and no back-to-back irrigations across soils and sowing dates, limited-water scheduling, canal-turn coverage, forecast postponement, bigha/acre bot parsing, report editing, rate limiting, STCR scaling and units, field conversion, validation, whole-bag budget invariants, exhaustive small-catalog optimality, zero needs/budget, compound N and schedule mass conservation, exact rain thresholds, provider failure, report persistence, CSRF, HTML escaping, one-page PDF exports, calendar folding, multilingual bot paths, expiry, signature checks, duplicate delivery retry and alert consent/daily deduplication. Live external deliveries and field agronomic accuracy require separate supervised validation.

PuLP 3.3 emits notices about APIs to be removed in PuLP 4. The dependency is bounded below 4; those deprecation notices are not failing model checks.

## Water-model notes

- Crop water use: FAO-56 single crop coefficients and stage lengths adapted for the Haridwar plains; effective (most-active) root zones are used for scheduling.
- Climate: 2015–2024 Roorkee daily ET₀ and rainfall from the Open-Meteo historical API, averaged by month. Rainfall uses the FAO/CROPWAT dependable-rain formula (plans for a moderately dry year).
- Calibration checks (tests): timely wheat on loam → 4–7 irrigations with CRI covered (IIWBR: 5–6); rice AWD saves 10–35% vs continuous flooding (IRRI: ~15–30%).
- Limitations: monthly averages cannot represent individual rain events; kharif crops often show zero planned irrigations in a normal monsoon. Always confirm with the khurpi test and the live forecast.
- Outbound HTTPS uses the operating-system trust store (`truststore`) so campus/institutional networks with their own certificate authorities work.

## Fonts and localization

The Noto Sans and Noto Sans Devanagari source fonts are redistributed under their included [SIL Open Font License](static/fonts/OFL.txt). A renamed combined **JalKhadd Sans** font supports Hindi shaping and Latin text in the same PDF word. Its build is reproducible:

```bash
python scripts/build_font.py
```

The generated font is already included; no runtime font download is necessary. ReportLab and HarfBuzz perform shaping. Web text uses the bundled Devanagari font and system Latin fonts.

Flask-Babel supplies the persistent EN/HI locale and `.po` navigation catalog. Paired template strings supply page copy. Detailed scientific notes/provenance remain in English with explicit Hindi summary warnings; this is not a claim that every technical diagnostic has been professionally translated.

## Deployment

The included `render.yaml` describes a **paid persistent-disk prototype**; creating it may incur charges. Deployment is not performed automatically. Set an HTTPS `PUBLIC_BASE_URL`, keep `COOKIE_SECURE=true`, configure provider secrets securely and back up the disk.

Alternatively, build the container and mount persistent storage:

```bash
docker build -t jal-khadd .
docker run --rm -p 8000:8000 \
  --env-file .env \
  -v jal-khadd-data:/app/instance \
  jal-khadd
```

The container runs a single Gunicorn worker. It does not launch an alert scheduler or send messages on startup. For non-container hosting:

```bash
gunicorn 'app:create_app()' --bind 0.0.0.0:8000 --workers 1 --timeout 90
```
