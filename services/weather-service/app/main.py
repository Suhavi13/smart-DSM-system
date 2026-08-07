
"""Independently runnable Open-Meteo integration service."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.shared.environment import load_service_environment

SERVICE_ROOT = Path(__file__).resolve().parents[1]
load_service_environment(SERVICE_ROOT)

from fastapi import Depends, FastAPI, HTTPException, Response

from services.shared.auth import CurrentUser, viewer_or_operator
from services.shared.cors import add_cors_middleware

from app.cache_service import cache
from app.schemas import WeatherForecastResponse
from app.weather_service import WeatherProviderError, get_weather_forecast


app = FastAPI(
    title="DSM Weather Service",
    version="1.0.0",
    description="Owns Open-Meteo access, normalization, retry logic, and caching.",
)
add_cors_middleware(app)


def _forecast(response: Response) -> dict:
    try:
        payload = get_weather_forecast()
        response.headers["X-Cache"] = payload["cacheStatus"].upper()
        return payload
    except WeatherProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get(
    "/api/v1/external/weather/forecast",
    response_model=WeatherForecastResponse,
)
def public_forecast(
    response: Response,
    user: CurrentUser = Depends(viewer_or_operator),
) -> dict:
    del user
    return _forecast(response)


@app.get(
    "/internal/weather/forecast",
    response_model=WeatherForecastResponse,
    include_in_schema=False,
)
def internal_forecast(response: Response) -> dict:
    """Cluster-internal contract used by recommendation-service."""
    return _forecast(response)


@app.get("/health")
def health() -> dict:
    redis_available = cache.ping()
    return {
        "status": "ok",
        "service": "weather-service",
        "version": "1.0.0",
        "provider": "Open-Meteo",
        "cache": {
            "enabled": cache.enabled,
            "status": (
                "connected"
                if redis_available
                else "unavailable"
                if cache.enabled
                else "disabled"
            ),
        },
    }
