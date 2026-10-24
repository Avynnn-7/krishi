from io import BytesIO

import pytest
from pypdf import PdfReader


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/advisory",
        "/simulator",
        "/about",
        "/bot",
        "/history",
        "/health",
        "/soil-card",
        "/water",
    ],
)
def test_pages_load(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_create_retrieve_export_delete(client, csrf, inputs):
    response = client.post("/api/advisory", json=inputs.model_dump(mode="json"), headers=csrf)
    assert response.status_code == 201
    report = response.json
    id_ = report["id"]
    assert len(id_) == 32
    result = client.get(f"/results/{id_}")
    assert result.status_code == 200
    assert b"expert review required" in result.data
    assert client.get(f"/results/{id_}/json").json == report
    assert id_.encode() in client.get("/history").data
    for language in ("en", "hi"):
        pdf = client.get(f"/results/{id_}/pdf?lang={language}")
        assert pdf.status_code == 200
        assert pdf.data.startswith(b"%PDF")
        parsed = PdfReader(BytesIO(pdf.data))
        assert len(parsed.pages) <= 2
        assert "2000" in parsed.pages[0].extract_text()
        if language == "en":
            assert "EXPERT REVIEW REQUIRED" in parsed.pages[0].extract_text()
    calendar = client.get(f"/results/{id_}/calendar.ics")
    assert calendar.data.count(b"BEGIN:VEVENT") == 3 + len(report["water"]["events"])
    assert b"STATUS:TENTATIVE" in calendar.data
    assert all(len(line) <= 75 for line in calendar.data.split(b"\r\n"))
    deleted = client.post(f"/results/{id_}/delete", headers=csrf)
    assert deleted.status_code == 302
    assert client.get(f"/results/{id_}").status_code == 404


def test_report_history_is_browser_scoped(app, client, csrf, inputs):
    id_ = client.post("/api/advisory", json=inputs.model_dump(mode="json"), headers=csrf).json["id"]
    other = app.test_client()
    other_csrf = {"X-CSRF-Token": other.get("/api/config").json["csrf"]}
    assert id_.encode() not in other.get("/history").data
    assert other.post(f"/results/{id_}/delete", headers=other_csrf).status_code == 403


def test_csrf_and_json_validation(client, csrf, inputs):
    assert client.post("/api/advisory", json=inputs.model_dump(mode="json")).status_code == 400
    for bad in ({}, [], {"area": "nan"}):
        assert client.post("/api/advisory", json=bad, headers=csrf).status_code == 422
    assert client.get("/results/not-found/pdf").status_code == 404


def test_language_switch_persists(client):
    result = client.get("/?lang=hi")
    assert 'lang="hi"'.encode() in result.data
    assert "खाद की योजना".encode() in result.data
    assert 'lang="hi"'.encode() in client.get("/advisory").data


def test_form_submission_with_manual_soil(client, csrf, inputs):
    payload = inputs.model_dump(mode="json")
    payload = {key: value for key, value in payload.items() if value is not None}
    payload.update(
        csrf=csrf["X-CSRF-Token"],
        soil_mode="card",
        soil_N="180",
        soil_P="45",
        soil_K="220",
        soil_basis="elemental",
    )
    response = client.post("/advisory", data=payload)
    assert response.status_code == 302
    report = client.get(response.location + "/json").json
    assert report["inputs"]["soil"]["P"] == 45
    assert report["method"].startswith("Soil-test-rating adjusted")
    assert report["soil_report"]["nutrient_ratings"] == {
        "N": "low",
        "P2O5": "high",
        "K2O": "medium",
    }


def test_form_errors_preserve_inputs(client, csrf, inputs):
    payload = inputs.model_dump(mode="json")
    payload = {key: value for key, value in payload.items() if value is not None}
    payload.update(csrf=csrf["X-CSRF-Token"], area="-1")
    response = client.post("/advisory", data=payload)
    assert response.status_code == 422
    assert b"Dhandera" in response.data


def test_user_content_is_escaped(client, csrf, inputs):
    payload = inputs.model_dump(mode="json")
    payload["village"] = "<script>alert(1)</script>"
    report = client.post("/api/advisory", json=payload, headers=csrf).json
    html = client.get(f"/results/{report['id']}").data
    assert b"<script>alert(1)</script>" not in html
    assert b"&lt;script&gt;" in html


def test_simulator_validation(client, csrf):
    assert (
        client.post("/simulator", data={"csrf": csrf["X-CSRF-Token"], "area_ha": "nan"}).status_code
        == 422
    )


def test_default_startup_creates_persistent_private_secret(monkeypatch, tmp_path):
    from app import ROOT, create_app

    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr("app.ROOT", tmp_path)
    config = {"TESTING": True, "DATA_DIR": ROOT / "data"}
    first, second = create_app(config), create_app(config)
    assert first.config["SECRET_KEY"] == second.config["SECRET_KEY"]
    assert len(first.config["SECRET_KEY"]) == 64
    assert (tmp_path / "instance/secret.key").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("crop", ["wheat", "sugarcane", "rice", "maize"])
def test_long_hindi_pdf_stays_within_two_pages(client, csrf, inputs, crop):
    payload = inputs.model_dump(mode="json")
    payload.update(village="परीक्षण " * 10, crop=crop, budget=10000)
    report = client.post("/api/advisory", json=payload, headers=csrf).json
    response = client.get(f"/results/{report['id']}/pdf?lang=hi")
    pdf = PdfReader(BytesIO(response.data))
    assert len(pdf.pages) <= 2
    assert "10000" in pdf.pages[0].extract_text()


def test_standalone_soil_and_water_tools(client):
    soil = client.get("/soil-card?N=180&P=30&K=220&zinc=0.4&area_ha=0.5&lang=hi")
    assert soil.status_code == 200
    assert "जिंक सल्फेट".encode() in soil.data
    bad = client.get("/soil-card?N=-1&P=1&K=1")
    assert bad.status_code == 422
    water = client.get(
        "/water?crop=wheat&sowing_date=2026-11-10&texture=loam&area=5&area_unit=bigha"
        "&bigha_m2=632.29&method=border&flow_lps=8&turn_hours=2&lang=en"
    )
    assert water.status_code == 200
    assert b"Irrigation methods compared" in water.data
    assert client.get("/water?crop=wheat&sowing_date=2026-11-10&method=rice_awd").status_code == 422
    assert client.get("/water?crop=wheat&sowing_date=bad").status_code == 422


def test_edit_and_recalculate_prefills_form(client, csrf, inputs):
    payload = inputs.model_dump(mode="json")
    payload.update(
        current_practice={"dap": 2},
        prices={"urea": 280},
        unavailable=["mop"],
        soil={"N": 180, "P": 30, "K": 220, "zinc": 0.4},
    )
    report = client.post("/api/advisory", json=payload, headers=csrf).json
    form = client.get(f"/advisory?from={report['id']}").data
    for fragment in (
        b'name="practice_dap"',
        b'value="2.0"',
        b'value="280.0"',
        b'name="unavailable_mop" value="1" checked',
        b'value="0.4"',
    ):
        assert fragment in form
    assert client.get("/advisory?from=missing").status_code == 404


def test_language_switch_keeps_query(client):
    page = client.get("/water?crop=wheat&sowing_date=2026-11-10")
    assert b"lang=hi" in page.data and b"crop=wheat" in page.data


def test_rate_limit_returns_429(app, client, csrf):
    app.config["RATE_LIMIT_PER_MINUTE"] = 3
    codes = [
        client.post("/api/bot", json={"text": "hi"}, headers=csrf).status_code for _ in range(4)
    ]
    assert codes == [200, 200, 200, 429]


@pytest.mark.parametrize(
    "query",
    [
        "crop=wheat&sowing_date=9999-12-31",
        "crop=wheat&sowing_date=2026-11-10&area=nan",
        "crop=wheat&sowing_date=2026-11-10&flow_lps=inf",
        "crop=cotton&sowing_date=2026-11-10",
        "crop=wheat&sowing_date=2026-11-10&texture=rock",
        "crop=wheat&sowing_date=2026-11-10&area_unit=bigha&bigha_m2=5",
    ],
)
def test_water_tool_rejects_hostile_inputs(client, query):
    assert client.get(f"/water?{query}").status_code == 422


def test_soil_tool_rejects_non_finite_area(client):
    assert client.get("/soil-card?N=200&P=10&K=100&area_ha=nan").status_code == 422


def test_autofill_geocode_and_voice_decipher_apis(client, csrf):
    af = client.get(
        "/api/autofill?block=Roorkee&village=Dhanauri&crop=wheat&area=5&area_unit=bigha"
    )
    assert af.status_code == 200
    data = af.json
    assert data["location"]["village"] == "Dhanauri"
    assert data["soil_profile"]["tier"] == "official_village"
    assert data["realtime_water"]["gross_cm"] > 0
    assert data["defaults"]["suggested_budget_rs"] >= 300

    geo = client.get("/api/geocode?q=https://maps.google.com/?q=29.9369,77.9564")
    assert geo.status_code == 200
    assert geo.json["village"] == "Dhanauri"
    assert geo.json["block"] == "Roorkee"

    voice = client.post(
        "/api/voice-decipher",
        headers=csrf,
        json={"text": "लक्सर के सुल्तानपुर में 2 एकड़ धान बजट 3000"},
    )
    assert voice.status_code == 200
    assert voice.json["parsed"]["block"] == "Laksar"
    assert voice.json["parsed"]["village"] == "Sultanpur"
    assert voice.json["parsed"]["crop"] == "rice"


def test_village_soil_hub_upload_and_auto_advisory(client, csrf, inputs):
    hub = client.get("/village-soil")
    assert hub.status_code == 200
    assert b"Pachauri et al. 2023" in hub.data

    csv_rows = (
        "block,village,village_hi,N,P,K,ph,organic_carbon,zinc,sulphur\n"
        "Roorkee,Padarsatha,पदरसाथा,160,38,240,7.4,0.52,0.48,9.0\n"
        "Roorkee,Padarsatha,पदरसाथा,180,42,260,7.6,0.58,0.52,11.0\n"
    )
    res = client.post(
        "/village-soil",
        data={"csrf": csrf["X-CSRF-Token"], "block": "Roorkee", "csv_rows": csv_rows},
    )
    assert res.status_code == 200
    assert b"Saved 1 official village soil profile" in res.data

    # Now submit advisory form in 'auto' soil mode for Padarsatha and verify averaged N=170, P=40, K=250 is used!
    form_data = {
        "csrf": csrf["X-CSRF-Token"],
        "block": "Roorkee",
        "village": "Padarsatha",
        "crop": "wheat",
        "sowing_date": "2026-11-10",
        "area": "5",
        "area_unit": "bigha",
        "bigha_m2": "632.29",
        "soil_mode": "auto",
        "budget": "2500",
    }
    post_res = client.post("/advisory", data=form_data)
    assert post_res.status_code == 302
    report = client.get(post_res.location + "/json").json
    assert report["inputs"]["soil_source"] == "official_village"
    assert report["inputs"]["soil"]["N"] == 170.0
    assert report["inputs"]["soil"]["P"] == 40.0
    assert report["inputs"]["soil"]["K"] == 250.0
