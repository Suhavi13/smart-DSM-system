from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session

from ..database import get_db
from ..decision_security import require_decision_key
from ..models import RecommendationDecision
from ..schemas import DecisionCreate, DecisionResponse


router = APIRouter(
    prefix="/api/v1/decisions",
    tags=["Decisions"],
)


@router.post(
    "",
    response_model=DecisionResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
def create_decision(
    payload: DecisionCreate,
    operator_label: Annotated[
        str,
        Depends(require_decision_key),
    ],
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=8,
            max_length=100,
        ),
    ],
    db: Session = Depends(get_db),
) -> RecommendationDecision:
    existing_idempotent_request = (
        db.query(RecommendationDecision)
        .filter(
            RecommendationDecision.idempotency_key
            == idempotency_key
        )
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
        comment=payload.comment.strip()
        if payload.comment
        else None,
        operator_label=operator_label,
        recommendation_snapshot=(
            payload.recommendation_snapshot
        ),
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
    _: Annotated[str, Depends(require_decision_key)],
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[RecommendationDecision]:
    return (
        db.query(RecommendationDecision)
        .order_by(
            RecommendationDecision.created_at.desc()
        )
        .limit(limit)
        .all()
    )