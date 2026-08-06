
"""Independently runnable Firebase authentication service."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.shared.environment import load_service_environment

SERVICE_ROOT = Path(__file__).resolve().parents[1]
load_service_environment(SERVICE_ROOT)

from fastapi import FastAPI

from services.shared.cors import add_cors_middleware

from app.router import router


app = FastAPI(
    title="DSM Authentication Service",
    version="1.0.0",
    description="Verifies Firebase ID tokens and returns trusted DSM roles.",
)
add_cors_middleware(app)
app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "auth-service", "version": "1.0.0"}
