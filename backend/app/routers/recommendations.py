"""Operator-only route that exposes explainable recommendations."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.auth import CurrentUser, operator_only

from ..database import get_db
from ..recommendation_service import evaluate_recommendations
from ..schemas import RecommendationServiceResponse


router = APIRouter(
    prefix="/api/v1/recommendations",
    tags=["Recommendations"],
)


@router.get("", response_model=RecommendationServiceResponse)
def get_recommendations(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(operator_only),
) -> dict:
    """Return recommendations only to authenticated Operators."""
    return evaluate_recommendations(db)
