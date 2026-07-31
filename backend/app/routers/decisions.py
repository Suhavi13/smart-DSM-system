"""Operator-only routes for approving or rejecting recommendations."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.auth import (
    CurrentUser,
    operator_only,
    require_csrf,
)

from ..database import get_db
from ..models import RecommendationDecision
from ..schemas import DecisionCreate, DecisionResponse


router = APIRouter(
    prefix="/api/v1/decisions",
    tags=["Decisions"],
)


def _operator_label(user: CurrentUser) -> str:
    """Create a readable audit label without trusting frontend identity data."""
    label = f"{user.name} ({user.username})"
    return label[:200]


@router.post(
    "",
    response_model=DecisionResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
def create_decision(
    payload: DecisionCreate,
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=8,
            max_length=100,
        ),
    ],
    db: Session = Depends(get_db),
    _: None = Depends(require_csrf),
    user: CurrentUser = Depends(operator_only),
) -> RecommendationDecision:
    existing_idempotent_request = (
        db.query(RecommendationDecision)
        .filter(RecommendationDecision.idempotency_key == idempotency_key)
        .first()
    )

    if existing_idempotent_request:
        return existing_idempotent_request

    existing_decision = (
        db.query(RecommendationDecision)
        .filter(
            RecommendationDecision.recommendation_id
            == payload.recommendation_id,
            RecommendationDecision.recommendation_version
            == payload.recommendation_version,
        )
        .first()
    )

    if existing_decision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This recommendation version has already "
                f"been {existing_decision.action}."
            ),
        )

    decision = RecommendationDecision(
        recommendation_id=payload.recommendation_id,
        recommendation_version=payload.recommendation_version,
        action=payload.action,
        comment=payload.comment.strip() if payload.comment else None,
        operator_label=_operator_label(user),
        recommendation_snapshot=payload.recommendation_snapshot,
        idempotency_key=idempotency_key,
    )

    db.add(decision)
    db.commit()
    db.refresh(decision)
    return decision


@router.get(
    "",
    response_model=list[DecisionResponse],
    response_model_by_alias=True,
)
def list_decisions(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(operator_only),
) -> list[RecommendationDecision]:
    return (
        db.query(RecommendationDecision)
        .order_by(RecommendationDecision.created_at.desc())
        .limit(limit)
        .all()
    )
