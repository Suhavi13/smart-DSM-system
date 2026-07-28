from fastapi.testclient import TestClient

from backend.app import main
from backend.app.dashboard_sensors import EXCLUDED_SENSOR_CODES
from backend.app.sensor_metadata import get_sensor_metadata
import fakeredis

from backend.app.cache_service import RedisJsonCache
from backend.app import weather_service
from backend.app.weather_service import (
    WeatherProviderError,
    normalize_weather_payload,
)


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


def test_conditions_sensor_metadata_uses_temperature_only():
    temperature = get_sensor_metadata(
        "20016_TL2", "Temperature", 6
    )

    assert temperature["display_unit"] == "°C"
    assert temperature["data_type"] == "ambient_temperature"
    assert "20016_TL5" in EXCLUDED_SENSOR_CODES


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
    normalized = {
        **normalize_weather_payload(sample_provider_payload()),
        "retrievedAt": "2026-07-22T19:00",
        "servedAt": "2026-07-22T19:00:01+00:00",
        "cacheStatus": "hit",
        "cacheTtlSeconds": 500,
        "isStale": False,
    }
    monkeypatch.setattr(main, "get_weather_forecast", lambda: normalized)

    response = client.get("/api/v1/external/weather/forecast")

    assert response.status_code == 200
    payload = response.json()
    assert payload["location"] == "Calgary, Alberta"
    assert payload["cacheStatus"] == "hit"
    assert payload["units"]["temperature"] == "°C"
    assert response.headers["x-cache"] == "HIT"
    assert len(payload["daily"]) == 2
    assert payload["daily"][0]["maximumTemperatureC"] == 27.0

def test_weather_uses_fresh_redis_cache(monkeypatch):
    monkeypatch.setenv("CACHE_ENABLED", "true")
    fake_cache = RedisJsonCache(
        client=fakeredis.FakeRedis(decode_responses=True)
    )
    normalized = normalize_weather_payload(sample_provider_payload())
    fake_cache.set_json(
        weather_service.WEATHER_CACHE_KEY,
        normalized,
        600,
    )
    monkeypatch.setattr(weather_service, "cache", fake_cache)
    monkeypatch.setattr(
        weather_service,
        "fetch_weather_forecast",
        lambda: (_ for _ in ()).throw(
            AssertionError("Provider should not be called on a cache hit.")
        ),
    )

    result = weather_service.get_weather_forecast()

    assert result["cacheStatus"] == "hit"
    assert result["isStale"] is False
    assert result["current"]["temperatureC"] == 23.4


def test_weather_uses_stale_cache_when_provider_fails(monkeypatch):
    monkeypatch.setenv("CACHE_ENABLED", "true")
    fake_cache = RedisJsonCache(
        client=fakeredis.FakeRedis(decode_responses=True)
    )
    normalized = normalize_weather_payload(sample_provider_payload())
    fake_cache.set_json(
        weather_service.WEATHER_STALE_CACHE_KEY,
        normalized,
        3600,
    )
    monkeypatch.setattr(weather_service, "cache", fake_cache)

    def fail_provider():
        raise WeatherProviderError("Provider unavailable.")

    monkeypatch.setattr(
        weather_service,
        "fetch_weather_forecast",
        fail_provider,
    )

    result = weather_service.get_weather_forecast()

    assert result["cacheStatus"] == "stale"
    assert result["isStale"] is True
    assert result["current"]["condition"] == "Partly cloudy"
