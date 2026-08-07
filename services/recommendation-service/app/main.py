
"""Independently runnable recommendation service."""

from __future__ import annotations

import os
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

from app.database import engine
from app.models import Recommendation
from app.router import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    # recommendation-service owns the recommendations table. Sensor tables are
    # read through the transitional shared PostgreSQL database.
    Recommendation.__table__.create(bind=engine, checkfirst=True)
    yield


app = FastAPI(
    title="DSM Recommendation Service",
    version="1.0.0",
    lifespan=lifespan,
    description=(
        "Evaluates rule-based and optional AI recommendations, then persists "
        "their snapshots and workflow status."
    ),
)
add_cors_middleware(app)
app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "recommendation-service",
        "version": "1.0.0",
        "weatherServiceUrl": os.getenv(
            "WEATHER_SERVICE_URL",
            "http://localhost:8003",
        ),
    }
