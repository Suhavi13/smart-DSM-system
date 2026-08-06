
"""Common CORS configuration for DSM HTTP services."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


DEFAULT_FRONTEND_ORIGINS = (
    "http://localhost:5500,http://localhost:5501,http://localhost:5173,"
    "http://127.0.0.1:5500,http://127.0.0.1:5501,http://127.0.0.1:5173"
)


def add_cors_middleware(app: FastAPI) -> None:
    origins = [
        origin.strip().rstrip("/")
        for origin in os.getenv(
            "FRONTEND_ORIGINS",
            DEFAULT_FRONTEND_ORIGINS,
        ).split(",")
        if origin.strip()
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Content-Type",
            "Authorization",
            "Idempotency-Key",
        ],
        expose_headers=["X-Cache"],
    )
