from datetime import datetime

import pytest

from app import ROOT, create_app
from engine.models import AdvisoryInput
from engine.service import load_catalog
from engine.timing import IST


@pytest.fixture
def inputs():
    return AdvisoryInput(
        block="Roorkee",
        village="Dhandera",
        crop="wheat",
        sowing_date=datetime.now(IST).date(),
        area=1,
        budget=2000,
    )


@pytest.fixture
def products():
    return load_catalog(ROOT / "data")[0]


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only-secret",
            "DATABASE_PATH": str(tmp_path / "test.db"),
            "WEATHER_ENABLED": False,
            "META_APP_SECRET": "",
            "META_ACCESS_TOKEN": "",
            "META_PHONE_NUMBER_ID": "",
            "META_VERIFY_TOKEN": "",
            "TWILIO_AUTH_TOKEN": "",
            "TWILIO_WEBHOOK_URL": "",
            "PUBLIC_BASE_URL": "https://example.test",
            "RATE_LIMIT_PER_MINUTE": 0,
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def csrf(client):
    return {"X-CSRF-Token": client.get("/api/config").json["csrf"]}
