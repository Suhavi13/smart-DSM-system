from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

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
) -> dict:
    """Evaluate transparent rules and return active recommendations."""
    return evaluate_recommendations(db)
