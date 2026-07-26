from backend.app.database import engine
from backend.app.models import RecommendationDecision


def main() -> None:
    RecommendationDecision.__table__.create(
        bind=engine,
        checkfirst=True,
    )

    print("recommendation_decisions table is ready.")


if __name__ == "__main__":
    main()