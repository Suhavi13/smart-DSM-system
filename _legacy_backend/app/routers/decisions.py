"""Operator-only routes for recommendation decisions and workflow resets."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.auth import CurrentUser, operator_only

from ..database import get_db
from ..models import Recommendation, RecommendationDecision
from ..recommendation_repository import (
    set_recommendation_pending,
    set_recommendation_status,
    upsert_recommendation,
)
from ..schemas import DecisionCreate, DecisionResetCreate, DecisionResponse


router = APIRouter(
    prefix="/api/v1/decisions",
    tags=["Decisions"],
)


def _operator_label(user: CurrentUser) -> str:
    """Create a readable audit label without trusting frontend identity data."""
    label = f"{user.name} ({user.username})"
    return label[:200]


def _find_stored_recommendation(
    db: Session,
    decision: RecommendationDecision,
) -> Recommendation | None:
    if decision.stored_recommendation_id is not None:
        stored = db.get(
            Recommendation,
            decision.stored_recommendation_id,
        )
        if stored is not None:
            return stored

    return (
        db.query(Recommendation)
        .filter(
            Recommendation.recommendation_key
            == decision.recommendation_id,
            Recommendation.recommendation_version
            == decision.recommendation_version,
        )
        .first()
    )


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
            RecommendationDecision.is_active.is_(True),
        )
        .first()
    )

    if existing_decision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This recommendation version has already "
                f"been {existing_decision.action}. Return it to pending "
                "before recording another decision."
            ),
        )

    stored_recommendation = (
        db.query(Recommendation)
        .filter(
            Recommendation.recommendation_key == payload.recommendation_id,
            Recommendation.recommendation_version
            == payload.recommendation_version,
        )
        .first()
    )

    if stored_recommendation is None:
        # Normally GET /recommendations has already stored the row. This
        # fallback keeps direct API decision requests consistent.
        stored_recommendation = upsert_recommendation(
            db,
            payload.recommendation_snapshot,
            generated_at=datetime.now(timezone.utc),
            recommendation_key=payload.recommendation_id,
            recommendation_version=payload.recommendation_version,
        )

    set_recommendation_status(stored_recommendation, payload.action)

    decision = RecommendationDecision(
        recommendation_id=payload.recommendation_id,
        recommendation_version=payload.recommendation_version,
        stored_recommendation_id=stored_recommendation.recommendation_id,
        action=payload.action,
        comment=payload.comment.strip() if payload.comment else None,
        operator_label=_operator_label(user),
        recommendation_snapshot=payload.recommendation_snapshot,
        idempotency_key=idempotency_key,
        is_active=True,
    )

    try:
        db.add(decision)
        db.commit()
        db.refresh(decision)
        return decision
    except Exception:
        db.rollback()
        raise


@router.post(
    "/{decision_id}/reset",
    response_model=DecisionResponse,
    response_model_by_alias=True,
)
def reset_decision_to_pending(
    decision_id: int,
    payload: DecisionResetCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(operator_only),
) -> RecommendationDecision:
    """Deactivate a decision and restore its recommendation to pending.

    The decision row is retained as audit history. A later approval or
    rejection creates a new active decision row.
    """
    decision = db.get(RecommendationDecision, decision_id)
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision not found.",
        )

    stored_recommendation = _find_stored_recommendation(db, decision)
    if stored_recommendation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The stored recommendation linked to this decision was not found.",
        )

    if not decision.is_active:
        # Keep repeated reset requests safe and idempotent.
        set_recommendation_pending(stored_recommendation)
        db.commit()
        db.refresh(decision)
        return decision

    decision.is_active = False
    decision.reverted_at = datetime.now(timezone.utc)
    decision.reverted_by = _operator_label(user)
    decision.revert_comment = (
        payload.comment.strip() if payload.comment else None
    )
    set_recommendation_pending(stored_recommendation)

    try:
        db.commit()
        db.refresh(decision)
        return decision
    except Exception:
        db.rollback()
        raise


@router.get(
    "",
    response_model=list[DecisionResponse],
    response_model_by_alias=True,
)
def list_decisions(
    limit: int = Query(default=100, ge=1, le=500),
    include_inactive: bool = Query(
        default=False,
        alias="includeInactive",
    ),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(operator_only),
) -> list[RecommendationDecision]:
    query = db.query(RecommendationDecision)
    if not include_inactive:
        query = query.filter(RecommendationDecision.is_active.is_(True))

    return (
        query.order_by(RecommendationDecision.created_at.desc())
        .limit(limit)
        .all()
    )
