"""Temporary decision-write guard kept for older non-production scripts."""

import os
import secrets
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Header, HTTPException, status


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")


def require_decision_key(
    supplied_key: Annotated[
        str | None,
        Header(alias="X-Decision-Key"),
    ] = None,
) -> str:
    app_environment = os.getenv(
        "APP_ENV",
        "development",
    ).strip().lower()

    configured_key = os.getenv(
        "DECISION_WRITE_KEY",
        "",
    ).strip()

    operator_label = os.getenv(
        "DECISION_OPERATOR_LABEL",
        "Temporary decision operator",
    ).strip()

    # The temporary shared-key mechanism must never be the
    # final protection used in a production deployment.
    if app_environment == "production":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Decision writes are disabled until production "
                "Operator authentication is configured."
            ),
        )

    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DECISION_WRITE_KEY is not configured.",
        )

    if not supplied_key or not secrets.compare_digest(
        supplied_key,
        configured_key,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid decision access key is required.",
        )

    return operator_label
