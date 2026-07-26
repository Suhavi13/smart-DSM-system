"""Weather provider integration for the dashboard.

The frontend calls the GBTAC backend instead of calling a third-party API
itself. This keeps provider configuration on the server and gives the
frontend a stable response shape if the provider changes later.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

import httpx


class WeatherProviderError(RuntimeError):
    """Raised when the configured weather provider cannot return valid data."""


WEATHER_API_BASE_URL = os.getenv(
    "WEATHER_API_BASE_URL",
    "https://api.open-meteo.com/v1/forecast",
).strip()
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "").strip()
WEATHER_LOCATION_NAME = os.getenv(
    "WEATHER_LOCATION_NAME", "Calgary, Alberta"
).strip()
WEATHER_LATITUDE = float(os.getenv("WEATHER_LATITUDE", "51.0447"))
WEATHER_LONGITUDE = float(os.getenv("WEATHER_LONGITUDE", "-114.0719"))
WEATHER_TIMEZONE = os.getenv(
    "WEATHER_TIMEZONE", "America/Edmonton"
).strip()
WEATHER_CACHE_SECONDS = max(
    60, int(os.getenv("WEATHER_CACHE_SECONDS", "600"))
)
WEATHER_REQUEST_TIMEOUT_SECONDS = max(
    1.0, float(os.getenv("WEATHER_REQUEST_TIMEOUT_SECONDS", "8"))
)

_cache_lock = threading.Lock()
_weather_cache: dict[str, Any] = {
    "expires_at": 0.0,
    "payload": None,
}


WMO_CONDITIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def describe_weather_code(code: int | None) -> str:
    if code is None:
        return "Unknown"
    return WMO_CONDITIONS.get(int(code), "Unknown")


def _required_sequence(
    container: dict[str, Any], key: str
) -> list[Any]:
    value = container.get(key)
    if not isinstance(value, list):
        raise WeatherProviderError(
            f"Weather provider response is missing daily field: {key}."
        )
    return value


def normalize_weather_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert the provider payload into the GBTAC dashboard contract."""
    current = payload.get("current")
    daily = payload.get("daily")

    if not isinstance(current, dict) or not isinstance(daily, dict):
        raise WeatherProviderError(
            "Weather provider response is missing current or daily data."
        )

    dates = _required_sequence(daily, "time")
    maximums = _required_sequence(daily, "temperature_2m_max")
    minimums = _required_sequence(daily, "temperature_2m_min")
    weather_codes = _required_sequence(daily, "weather_code")
    precipitation = _required_sequence(
        daily, "precipitation_probability_max"
    )

    lengths = {
        len(dates),
        len(maximums),
        len(minimums),
        len(weather_codes),
        len(precipitation),
    }
    if len(lengths) != 1:
        raise WeatherProviderError(
            "Weather provider returned daily arrays with different lengths."
        )

    daily_items = []
    for index, date in enumerate(dates):
        code = weather_codes[index]
        daily_items.append(
            {
                "date": date,
                "maximumTemperatureC": maximums[index],
                "minimumTemperatureC": minimums[index],
                "precipitationProbabilityPercent": precipitation[index],
                "weatherCode": code,
                "condition": describe_weather_code(code),
            }
        )

    current_code = current.get("weather_code")

    return {
        "location": WEATHER_LOCATION_NAME,
        "latitude": payload.get("latitude", WEATHER_LATITUDE),
        "longitude": payload.get("longitude", WEATHER_LONGITUDE),
        "timezone": payload.get("timezone", WEATHER_TIMEZONE),
        "source": "Open-Meteo",
        "sourceUrl": "https://open-meteo.com/",
        "retrievedAt": current.get("time"),
        "current": {
            "temperatureC": current.get("temperature_2m"),
            "humidityPercent": current.get("relative_humidity_2m"),
            "weatherCode": current_code,
            "condition": describe_weather_code(current_code),
        },
        "daily": daily_items,
    }


def _provider_parameters() -> dict[str, Any]:
    parameters: dict[str, Any] = {
        "latitude": WEATHER_LATITUDE,
        "longitude": WEATHER_LONGITUDE,
        "current": (
            "temperature_2m,relative_humidity_2m,weather_code"
        ),
        "daily": (
            "weather_code,temperature_2m_max,temperature_2m_min,"
            "precipitation_probability_max"
        ),
        "timezone": WEATHER_TIMEZONE,
        "forecast_days": 7,
    }

    if WEATHER_API_KEY:
        parameters["apikey"] = WEATHER_API_KEY

    return parameters


def fetch_weather_forecast() -> dict[str, Any]:
    """Fetch and normalize a forecast from the configured provider."""
    try:
        response = httpx.get(
            WEATHER_API_BASE_URL,
            params=_provider_parameters(),
            timeout=WEATHER_REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": "GBTAC-Dashboard/0.2.2"},
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise WeatherProviderError(
            "Weather provider could not be reached or returned invalid data."
        ) from error

    if not isinstance(payload, dict):
        raise WeatherProviderError(
            "Weather provider returned an unexpected response."
        )

    return normalize_weather_payload(payload)


def get_weather_forecast() -> dict[str, Any]:
    """Return a short-lived cached forecast to avoid one API call per viewer."""
    now = time.monotonic()

    with _cache_lock:
        cached_payload = _weather_cache.get("payload")
        expires_at = float(_weather_cache.get("expires_at") or 0.0)
        if cached_payload is not None and now < expires_at:
            return cached_payload

    payload = fetch_weather_forecast()

    with _cache_lock:
        _weather_cache["payload"] = payload
        _weather_cache["expires_at"] = now + WEATHER_CACHE_SECONDS

    return payload


def clear_weather_cache() -> None:
    """Clear the cache for tests and controlled operational refreshes."""
    with _cache_lock:
        _weather_cache["payload"] = None
        _weather_cache["expires_at"] = 0.0
