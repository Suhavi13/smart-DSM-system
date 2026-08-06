
"""Independently runnable sensor and dashboard service."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.shared.environment import load_service_environment

SERVICE_ROOT = Path(__file__).resolve().parents[1]
load_service_environment(SERVICE_ROOT)

from fastapi import FastAPI

from services.shared.cors import add_cors_middleware

from app.api import router
from app.cache_service import cache
from app.database import Base, engine
from app import models  # noqa: F401 - registers the owned tables


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="DSM Sensor Service",
    version="1.0.0",
    lifespan=lifespan,
    description=(
        "Owns the historical sensor inventory, readings, averages, and "
        "dashboard aggregation endpoints."
    ),
)
add_cors_middleware(app)
app.include_router(router)


@app.get("/health")
def health() -> dict:
    redis_available = cache.ping()
    return {
        "status": "ok",
        "service": "sensor-service",
        "version": "1.0.0",
        "datasetType": "historical",
        "cache": {
            "enabled": cache.enabled,
            "provider": "Redis",
            "status": (
                "connected"
                if redis_available
                else "unavailable"
                if cache.enabled
                else "disabled"
            ),
        },
    }
