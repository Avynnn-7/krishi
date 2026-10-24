from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from bot.alerts import dispatch_alerts
from engine.timing import IST
from storage import connect


@pytest.mark.parametrize("rain,expected", [(20, 0), (20.1, 1)])
def test_alert_threshold_opt_in_and_daily_deduplication(app, rain, expected):
    app.config.update(
        META_ALERT_TEMPLATE="rain_alert",
        META_ACCESS_TOKEN="fake",
        META_PHONE_NUMBER_ID="fake",
        WEATHER_ENABLED=True,
    )
    today = datetime.now(IST).date()
    with connect(app.config["DATABASE_PATH"]) as db:
        db.execute(
            "INSERT INTO subscriptions VALUES (?, ?, ?, ?, ?, NULL)",
            ("hash", "919999999999", 29.85, 77.88, today.isoformat()),
        )
    weather = {
        "status": "live",
        "days": [
            {"date": today.isoformat(), "rain_mm": rain},
            {"date": (today + timedelta(days=1)).isoformat(), "rain_mm": 0},
        ],
    }
    with (
        patch("bot.alerts.get_forecast", return_value=weather),
        patch("bot.alerts.send_payload") as send,
    ):
        assert dispatch_alerts(app.config) == expected
        assert dispatch_alerts(app.config) == 0
        assert send.call_count == expected
        if expected:
            assert send.call_args.args[2]["type"] == "template"


def test_alerts_require_explicit_configuration(app):
    with pytest.raises(ValueError, match="require"):
        dispatch_alerts(app.config)


def test_missing_today_does_not_trigger_alert_for_later_rain(app):
    app.config.update(
        META_ALERT_TEMPLATE="rain",
        META_ACCESS_TOKEN="fake",
        META_PHONE_NUMBER_ID="fake",
        WEATHER_ENABLED=True,
    )
    today = datetime.now(IST).date()
    with connect(app.config["DATABASE_PATH"]) as db:
        db.execute(
            "INSERT INTO subscriptions VALUES (?, ?, ?, ?, ?, NULL)",
            ("hash", "919999999999", 29.85, 77.88, today.isoformat()),
        )
    forecast = {
        "status": "live",
        "days": [{"date": (today + timedelta(days=i)).isoformat(), "rain_mm": 30} for i in (1, 2)],
    }
    with (
        patch("bot.alerts.get_forecast", return_value=forecast),
        patch("bot.alerts.send_payload") as send,
    ):
        assert dispatch_alerts(app.config) == 0
        send.assert_not_called()
