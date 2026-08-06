
"""Independently runnable recommendation-decision workflow service."""

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

from app.database import engine
from app.models import Recommendation, RecommendationDecision
from app.router import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    # The recommendation table is needed for the decision fallback and status
    # update. checkfirst keeps this safe when recommendation-service created it.
    Recommendation.__table__.create(bind=engine, checkfirst=True)
    RecommendationDecision.__table__.create(bind=engine, checkfirst=True)
    yield


app = FastAPI(
    title="DSM Decision Service",
    version="1.0.0",
    lifespan=lifespan,
    description=(
        "Stores operator approvals, rejections, resets, and immutable audit "
        "history for generated recommendations."
    ),
)
add_cors_middleware(app)
app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "decision-service", "version": "1.0.0"}
