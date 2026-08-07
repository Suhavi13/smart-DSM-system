
"""HTTP client for the independently deployed weather service."""

from __future__ import annotations

import os
from typing import Any

import httpx


class WeatherProviderError(RuntimeError):
    """Raised when weather-service cannot supply a usable response."""


WEATHER_SERVICE_URL = os.getenv(
    "WEATHER_SERVICE_URL",
    "http://localhost:8003",
).strip().rstrip("/")
WEATHER_SERVICE_TIMEOUT_SECONDS = max(
    1.0,
    float(os.getenv("WEATHER_SERVICE_TIMEOUT_SECONDS", "10")),
)


def get_weather_forecast() -> dict[str, Any]:
    try:
        response = httpx.get(
            f"{WEATHER_SERVICE_URL}/internal/weather/forecast",
            timeout=WEATHER_SERVICE_TIMEOUT_SECONDS,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise WeatherProviderError(
            "The recommendation service could not reach weather-service."
        ) from error

    if not isinstance(payload, dict):
        raise WeatherProviderError("weather-service returned an invalid response.")
    return payload
