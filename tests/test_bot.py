import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from bot.meta_api import DeliveryError
from bot.parser import parse_crop, parse_number, parse_soil
from storage import connect


@pytest.mark.parametrize("text", ["₹2000", "2000rs", "२०००", "2000 rupees"])
def test_budget_parser(text):
    assert parse_number(text) == 2000


@pytest.mark.parametrize("text", ["-100", "two thousand", "1e3", "2000 and 3000", "NaN", "1/2"])
def test_unsafe_numeric_parsing_rejected(text):
    with pytest.raises(ValueError):
        parse_number(text)


def test_hindi_and_hinglish():
    assert parse_crop("गेहूं") == "wheat"
    assert parse_crop("ganna") == "sugarcane"
    assert parse_crop("३") == "rice"
    assert parse_soil("१८०/४५/२२०") == (180, 45, 220)
    with pytest.raises(ValueError):
        parse_soil("180,-45,220")


def conversation(client, csrf, card=False):
    messages = ["नमस्ते", "1", "Dhandera", "gehun", "1", "2026-11-01", "3", "नहीं", "नहीं", "2000"]
    messages.extend(["1", "1", "180,45,220"] if card else ["2"])
    for text in messages:
        response = client.post("/api/bot", headers=csrf, json={"text": text})
        assert response.status_code == 200, response.json
    return response.json


@pytest.mark.parametrize("card", [True, False])
def test_complete_conversation_uses_persisted_report(client, csrf, app, card):
    reply = conversation(client, csrf, card)
    assert "खरीदारी" in reply["text"]
    assert "₹2000" in reply["text"]
    assert "सिंचाई" in reply["text"]
    with connect(app.config["DATABASE_PATH"]) as db:
        report = json.loads(db.execute("SELECT payload FROM recommendations").fetchone()["payload"])
    assert report["inputs"]["area"] == 1
    assert (report["inputs"]["soil"] is not None) == card
    pdf = client.post("/api/bot", headers=csrf, json={"text": "1"}).json
    assert "/pdf?lang=hi" in pdf["document"]
    alert = client.post("/api/bot", headers=csrf, json={"text": "2"}).json
    assert "चालू नहीं" in alert["text"]
    client.post("/api/bot", headers=csrf, json={"text": "DELETE"})
    with connect(app.config["DATABASE_PATH"]) as db:
        assert db.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0] == 0


def test_bad_input_help_and_expiry(client, csrf, app):
    client.post("/api/bot", headers=csrf, json={"text": "hi"})
    for _ in range(3):
        response = client.post("/api/bot", headers=csrf, json={"text": "99"})
    assert "restart" in response.json["text"]
    with connect(app.config["DATABASE_PATH"]) as db:
        db.execute(
            "UPDATE bot_sessions SET updated_at=?",
            ((datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat(),),
        )
    result = client.post("/api/bot", headers=csrf, json={"text": "1"})
    assert "स्वागत" in result.json["text"]


def test_browser_reload_restores_current_prompt(client, csrf):
    client.post("/api/bot", headers=csrf, json={"text": "hi"})
    client.post("/api/bot", headers=csrf, json={"text": "1"})
    response = client.get("/bot")
    assert "गाँव का नाम लिखें।".encode() in response.data


def test_stop_removes_subscription_even_after_session_expiry(client, csrf, app):
    from bot.state_machine import session_key

    client.post("/api/bot", headers=csrf, json={"text": "hi"})
    with client.session_transaction() as session:
        key = session_key("demo:" + session["bot_id"], app.config["SECRET_KEY"])
    with connect(app.config["DATABASE_PATH"]) as db:
        db.execute(
            "INSERT INTO subscriptions VALUES (?, ?, ?, ?, ?, NULL)",
            (key, "919999999999", 29.85, 77.88, datetime.now(timezone.utc).isoformat()),
        )
        db.execute("DELETE FROM bot_sessions")
    response = client.post("/api/bot", headers=csrf, json={"text": "STOP"})
    assert response.status_code == 200
    with connect(app.config["DATABASE_PATH"]) as db:
        assert db.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0] == 0


def signed_payload(app, message_id="m1", body="hi"):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "phone-id"},
                            "messages": [
                                {
                                    "id": message_id,
                                    "from": "919999999999",
                                    "type": "text",
                                    "text": {"body": body},
                                }
                            ],
                        }
                    }
                ]
            }
        ],
    }
    raw = json.dumps(payload).encode()
    signature = (
        "sha256="
        + hmac.new(app.config["META_APP_SECRET"].encode(), raw, hashlib.sha256).hexdigest()
    )
    return raw, {"Content-Type": "application/json", "X-Hub-Signature-256": signature}


def test_webhook_configuration_and_verification(client, app):
    assert client.post("/webhook/whatsapp", json={}).status_code == 503
    app.config.update(META_VERIFY_TOKEN="verify")
    assert (
        client.get(
            "/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=verify&hub.challenge=123"
        ).data
        == b"123"
    )
    assert (
        client.get("/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=wrong").status_code == 403
    )


def test_signed_webhook_deduplication_and_failed_delivery_retry(client, app):
    app.config.update(
        META_APP_SECRET="test-app", META_ACCESS_TOKEN="fake-token", META_PHONE_NUMBER_ID="phone-id"
    )
    raw, headers = signed_payload(app)
    assert (
        client.post("/webhook/whatsapp", data=raw, content_type="application/json").status_code
        == 403
    )
    with patch("bot.webhook.send_reply", side_effect=DeliveryError("failed")):
        assert client.post("/webhook/whatsapp", data=raw, headers=headers).status_code == 502
    with patch("bot.webhook.send_reply") as send:
        assert client.post("/webhook/whatsapp", data=raw, headers=headers).status_code == 200
        assert client.post("/webhook/whatsapp", data=raw, headers=headers).status_code == 200
        send.assert_called_once()
    with connect(app.config["DATABASE_PATH"]) as db:
        assert db.execute("SELECT COUNT(*) FROM inbox").fetchone()[0] == 1
        state = json.loads(db.execute("SELECT payload FROM bot_sessions").fetchone()[0])
        assert state["step"] == "BLOCK"


def test_twilio_requires_signature(client, app):
    app.config.update(
        TWILIO_AUTH_TOKEN="fake", TWILIO_WEBHOOK_URL="https://example.test/webhook/twilio"
    )
    assert client.post("/webhook/twilio", data={"Body": "hi"}).status_code == 403


@pytest.mark.parametrize(
    "text,unit,hectares",
    [
        ("2 bigha", "bigha", 0.126458),
        ("२ बीघा", "bigha", 0.126458),
        ("1.5 acre", "acre", 0.607029),
        ("0.5", "ha", 0.5),
        ("0.5 ha", "ha", 0.5),
    ],
)
def test_area_parser_units(text, unit, hectares):
    from bot.parser import parse_area
    from engine.models import AdvisoryInput

    area = parse_area(text)
    assert area["area_unit"] == unit
    model = AdvisoryInput(
        block="Roorkee", village="X", crop="wheat", sowing_date="2026-11-10", budget=1, **area
    )
    assert model.area_ha == pytest.approx(hectares, rel=1e-4)


@pytest.mark.parametrize("text", ["2 hectares of land", "0", "5000 ha", "bigha"])
def test_area_parser_rejects(text):
    from bot.parser import parse_area

    with pytest.raises(ValueError):
        parse_area(text)


def test_spoken_hindi_area_and_voice_nlu():
    from app import ROOT
    from bot.parser import decipher_voice_utterance, parse_area, parse_spoken_budget
    from engine.service import load_blocks

    area = parse_area("पाँच बीघा")
    assert area == {"area": 5.0, "area_unit": "bigha", "bigha_m2": 632.29}
    assert parse_spoken_budget("दो हज़ार रुपये") == 2000.0
    assert parse_spoken_budget("ढाई हजार") == 2500.0
    parsed = decipher_voice_utterance(
        "रुड़की के ढंडेरा गाँव में पाँच बीघा गेहूं बोना है बजट दो हज़ार रुपये",
        load_blocks(ROOT / "data"),
    )
    assert parsed["block"] == "Roorkee"
    assert parsed["village"] == "Dhandera"
    assert parsed["crop"] == "wheat"
    assert parsed["area"] == 5.0
    assert parsed["area_unit"] == "bigha"
    assert parsed["budget"] == 2000.0


def test_concise_farmer_bot_flow_with_auto_soil(client, csrf, app):
    # Farmer only answers: 1 (Roorkee) -> 1 (Dhandera) -> 1 (Wheat) -> पाँच बीघा -> दो हज़ार -> 3 (Auto official soil)
    steps = ["नमस्ते", "1", "1", "1", "पाँच बीघा", "दो हज़ार", "3"]
    for msg in steps:
        res = client.post("/api/bot", headers=csrf, json={"text": msg})
        assert res.status_code == 200
    data = res.json
    assert "खरीदारी" in data["text"]
    assert "सिंचाई" in data["text"]
    assert data["options"]
    with connect(app.config["DATABASE_PATH"]) as db:
        report = json.loads(db.execute("SELECT payload FROM recommendations").fetchone()["payload"])
    assert report["inputs"]["village"] == "Dhandera"
    assert report["inputs"]["soil_source"] == "official_village"
    assert report["inputs"]["latitude"] == pytest.approx(29.8328, abs=0.01)


def test_one_shot_voice_sentence_completes_bot_plan(client, csrf):
    res = client.post(
        "/api/bot",
        headers=csrf,
        json={"text": "भगवानपुर के चूड़ियाला में 10 बीघा गन्ना बजट 5000"},
    )
    assert res.status_code == 200
    data = res.json
    assert data["step"] == "RESULT"
    assert "खरीदारी" in data["text"]
    assert "गन्ना" in data["text"]
