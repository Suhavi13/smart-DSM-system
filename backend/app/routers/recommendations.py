from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.auth import CurrentUser, viewer_or_operator

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
    user: CurrentUser = Depends(viewer_or_operator),
) -> dict:
    """Return recommendations to assigned Viewers and Operators."""
    return evaluate_recommendations(db)
