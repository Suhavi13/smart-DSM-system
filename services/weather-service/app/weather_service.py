"""Open-Meteo integration and Redis-backed weather caching.

The browser calls the GBTAC backend, never the provider directly. Provider
payloads are normalized into a stable application-owned contract so a future
weather provider can be substituted without rewriting the dashboard.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from .cache_service import cache

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


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
WEATHER_STALE_CACHE_SECONDS = max(
    WEATHER_CACHE_SECONDS,
    int(os.getenv("WEATHER_STALE_CACHE_SECONDS", "21600")),
)
WEATHER_REQUEST_TIMEOUT_SECONDS = max(
    1.0, float(os.getenv("WEATHER_REQUEST_TIMEOUT_SECONDS", "8"))
)
WEATHER_MAX_ATTEMPTS = min(
    3, max(1, int(os.getenv("WEATHER_MAX_ATTEMPTS", "2")))
)

WEATHER_CACHE_KEY = "external:weather:forecast"
WEATHER_STALE_CACHE_KEY = "external:weather:forecast:last-success"


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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    """Convert Open-Meteo data into the application-owned weather contract."""
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
    for index, forecast_date in enumerate(dates):
        code = weather_codes[index]
        daily_items.append(
            {
                "date": forecast_date,
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
        "latitude": float(
            payload.get("latitude", WEATHER_LATITUDE)
        ),
        "longitude": float(
            payload.get("longitude", WEATHER_LONGITUDE)
        ),
        "timezone": payload.get("timezone", WEATHER_TIMEZONE),
        "source": "Open-Meteo",
        "sourceUrl": "https://open-meteo.com/",
        "providerRetrievedAt": current.get("time"),
        "units": {
            "temperature": "°C",
            "humidity": "%",
            "precipitationProbability": "%",
        },
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
    """Fetch, validate, and normalize the configured weather provider."""
    last_error: Exception | None = None

    for attempt in range(1, WEATHER_MAX_ATTEMPTS + 1):
        try:
            response = httpx.get(
                WEATHER_API_BASE_URL,
                params=_provider_parameters(),
                timeout=WEATHER_REQUEST_TIMEOUT_SECONDS,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "GBTAC-Dashboard/0.4.0",
                },
            )
            response.raise_for_status()
            payload = response.json()

            if not isinstance(payload, dict):
                raise WeatherProviderError(
                    "Weather provider returned an unexpected response."
                )

            return normalize_weather_payload(payload)
        except (
            httpx.HTTPError,
            ValueError,
            WeatherProviderError,
        ) as error:
            last_error = error
            if attempt < WEATHER_MAX_ATTEMPTS:
                time.sleep(0.25 * (2 ** (attempt - 1)))

    raise WeatherProviderError(
        "Weather provider could not be reached or returned invalid data."
    ) from last_error


def _with_cache_metadata(
    payload: dict[str, Any],
    *,
    cache_status: str,
    is_stale: bool,
    cache_ttl_seconds: int | None,
) -> dict[str, Any]:
    return {
        **payload,
        "retrievedAt": payload.get("providerRetrievedAt"),
        "servedAt": _utc_now_iso(),
        "cacheStatus": cache_status,
        "cacheTtlSeconds": cache_ttl_seconds,
        "isStale": is_stale,
    }


def get_weather_forecast(
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Return fresh Redis data, fetch on miss, or stale data on provider failure."""
    if not force_refresh:
        cached_payload = cache.get_json(WEATHER_CACHE_KEY)
        if isinstance(cached_payload, dict):
            return _with_cache_metadata(
                cached_payload,
                cache_status="hit",
                is_stale=False,
                cache_ttl_seconds=cache.ttl(WEATHER_CACHE_KEY),
            )

    try:
        payload = fetch_weather_forecast()
    except WeatherProviderError:
        stale_payload = cache.get_json(WEATHER_STALE_CACHE_KEY)
        if isinstance(stale_payload, dict):
            return _with_cache_metadata(
                stale_payload,
                cache_status="stale",
                is_stale=True,
                cache_ttl_seconds=cache.ttl(
                    WEATHER_STALE_CACHE_KEY
                ),
            )
        raise

    fresh_cached = cache.set_json(
        WEATHER_CACHE_KEY,
        payload,
        WEATHER_CACHE_SECONDS,
    )
    cache.set_json(
        WEATHER_STALE_CACHE_KEY,
        payload,
        WEATHER_STALE_CACHE_SECONDS,
    )

    return _with_cache_metadata(
        payload,
        cache_status="miss" if fresh_cached else "bypass",
        is_stale=False,
        cache_ttl_seconds=(
            WEATHER_CACHE_SECONDS if fresh_cached else None
        ),
    )


def clear_weather_cache() -> None:
    cache.delete(WEATHER_CACHE_KEY)
    cache.delete(WEATHER_STALE_CACHE_KEY)
