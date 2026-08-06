
"""Operator-only endpoint that evaluates and stores recommendations."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from services.shared.auth import CurrentUser, operator_only

from .database import get_db
from .recommendation_repository import persist_generated_recommendations
from .recommendation_service import evaluate_recommendations
from .schemas import RecommendationServiceResponse


router = APIRouter(
    prefix="/api/v1/recommendations",
    tags=["Recommendations"],
)


@router.get("", response_model=RecommendationServiceResponse)
def get_recommendations(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(operator_only),
) -> dict:
    del user
    result = evaluate_recommendations(db)
    persist_generated_recommendations(db, result)
    return result
