from unittest.mock import Mock, patch

import pytest
import requests

from engine.weather import get_forecast


def test_disabled_and_missing_coordinates_do_not_call_provider():
    with patch("engine.weather.requests.get") as get:
        assert get_forecast(29.85, 77.88)["status"] == "unavailable"
        assert get_forecast(None, None, True)["status"] == "unavailable"
        get.assert_not_called()


@pytest.mark.parametrize("rain", [None, float("nan"), -1, True, "3"])
def test_bad_provider_values_are_unknown(rain):
    response = Mock()
    response.json.return_value = {"daily": {"time": ["2026-10-20"], "precipitation_sum": [rain]}}
    with patch("engine.weather.requests.get", return_value=response):
        assert get_forecast(29.85, 77.88, True)["status"] == "unavailable"


def test_provider_timeout_is_unknown(caplog):
    with patch("engine.weather.requests.get", side_effect=requests.Timeout):
        assert get_forecast(29.85, 77.88, True)["status"] == "unavailable"
    assert "unavailable" in caplog.text


def test_weather_only_sends_coordinates_and_public_forecast_options():
    response = Mock()
    response.json.return_value = {"daily": {"time": ["2026-10-20"], "precipitation_sum": [5]}}
    with patch("engine.weather.requests.get", return_value=response) as get:
        forecast = get_forecast(29.85, 77.88, True)
    assert forecast["status"] == "live"
    assert forecast["days"] == [{"date": "2026-10-20", "rain_mm": 5}]
    assert set(get.call_args.kwargs["params"]) == {
        "latitude",
        "longitude",
        "daily",
        "timezone",
        "forecast_days",
    }
