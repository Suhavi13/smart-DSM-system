from fastapi.testclient import TestClient

from backend.app import main
from backend.app.sensor_metadata import get_sensor_metadata
from backend.app.weather_service import normalize_weather_payload


def sample_provider_payload():
    return {
        "latitude": 51.04,
        "longitude": -114.07,
        "timezone": "America/Edmonton",
        "current": {
            "time": "2026-07-22T19:00",
            "temperature_2m": 23.4,
            "relative_humidity_2m": 41,
            "weather_code": 2,
        },
        "daily": {
            "time": ["2026-07-22", "2026-07-23"],
            "temperature_2m_max": [27.0, 25.5],
            "temperature_2m_min": [14.0, 13.5],
            "weather_code": [2, 61],
            "precipitation_probability_max": [10, 65],
        },
    }


def test_conditions_sensor_metadata_supports_chart_pair():
    temperature = get_sensor_metadata(
        "20016_TL2", "Temperature", 6
    )
    air_quality = get_sensor_metadata(
        "20016_TL5", "CO2_Sensor", 44
    )

    assert temperature["display_unit"] == "°C"
    assert temperature["data_type"] == "ambient_temperature"
    assert air_quality["display_unit"] == "ppm"
    assert air_quality["data_type"] == "co2"


def test_weather_payload_is_normalized():
    result = normalize_weather_payload(sample_provider_payload())

    assert result["source"] == "Open-Meteo"
    assert result["current"]["temperatureC"] == 23.4
    assert result["current"]["condition"] == "Partly cloudy"
    assert result["daily"][1]["condition"] == "Slight rain"
    assert result["daily"][1]["precipitationProbabilityPercent"] == 65


def test_weather_endpoint_returns_dashboard_contract(
    client: TestClient, monkeypatch
):
    normalized = normalize_weather_payload(sample_provider_payload())
    monkeypatch.setattr(main, "get_weather_forecast", lambda: normalized)

    response = client.get("/api/v1/external/weather/forecast")

    assert response.status_code == 200
    payload = response.json()
    assert payload["location"] == "Calgary, Alberta"
    assert len(payload["daily"]) == 2
    assert payload["daily"][0]["maximumTemperatureC"] == 27.0
