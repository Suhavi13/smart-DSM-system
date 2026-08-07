"""Database persistence tests for recommendations and decisions."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app import recommendation_service
from backend.app.models import Recommendation, RecommendationDecision
from backend.tests.test_recommendations import (
    seed_recommendation_inputs,
    weather_payload,
)


def test_decision_links_to_stored_recommendation_and_updates_status(
    client: TestClient,
    db_session: Session,
    monkeypatch,
):
    seed_recommendation_inputs(db_session)
    monkeypatch.setattr(
        recommendation_service,
        "get_weather_forecast",
        weather_payload,
    )

    recommendation_response = client.get("/api/v1/recommendations")
    assert recommendation_response.status_code == 200
    snapshot = recommendation_response.json()["recommendations"][0]

    decision_response = client.post(
        "/api/v1/decisions",
        headers={"Idempotency-Key": "recommendation-storage-test"},
        json={
            "recommendationId": snapshot["recommendationId"],
            "recommendationVersion": snapshot["recommendationVersion"],
            "action": "approved",
            "comment": "Approved during test.",
            "recommendationSnapshot": snapshot,
        },
    )

    assert decision_response.status_code == 201

    stored = (
        db_session.query(Recommendation)
        .filter(
            Recommendation.recommendation_key
            == snapshot["recommendationId"],
            Recommendation.recommendation_version
            == snapshot["recommendationVersion"],
        )
        .one()
    )
    decision = db_session.query(RecommendationDecision).one()

    assert (
        decision_response.json()["storedRecommendationId"]
        == stored.recommendation_id
    )
    assert stored.status == "approved"
    assert decision.stored_recommendation_id == stored.recommendation_id
    assert decision.action == "approved"


def test_decision_can_return_to_pending_without_deleting_audit_history(
    client: TestClient,
    db_session: Session,
    monkeypatch,
):
    seed_recommendation_inputs(db_session)
    monkeypatch.setattr(
        recommendation_service,
        "get_weather_forecast",
        weather_payload,
    )

    snapshot = client.get(
        "/api/v1/recommendations"
    ).json()["recommendations"][0]

    approved = client.post(
        "/api/v1/decisions",
        headers={"Idempotency-Key": "approve-before-reset-test"},
        json={
            "recommendationId": snapshot["recommendationId"],
            "recommendationVersion": snapshot["recommendationVersion"],
            "action": "approved",
            "comment": "Initial approval.",
            "recommendationSnapshot": snapshot,
        },
    )
    assert approved.status_code == 201
    original_decision_id = approved.json()["decisionId"]

    reset = client.post(
        f"/api/v1/decisions/{original_decision_id}/reset",
        json={"comment": "Reopened for another review."},
    )
    assert reset.status_code == 200
    assert reset.json()["isActive"] is False
    assert reset.json()["revertedAt"] is not None
    assert reset.json()["revertComment"] == "Reopened for another review."

    stored = (
        db_session.query(Recommendation)
        .filter(
            Recommendation.recommendation_key
            == snapshot["recommendationId"],
            Recommendation.recommendation_version
            == snapshot["recommendationVersion"],
        )
        .one()
    )
    original = db_session.get(
        RecommendationDecision,
        original_decision_id,
    )
    assert stored.status == "pending"
    assert original is not None
    assert original.is_active is False

    # The normal list endpoint returns current decisions only.
    assert client.get("/api/v1/decisions").json() == []

    # Audit history remains available when explicitly requested.
    history = client.get(
        "/api/v1/decisions?includeInactive=true"
    ).json()
    assert len(history) == 1
    assert history[0]["decisionId"] == original_decision_id
    assert history[0]["isActive"] is False

    rejected = client.post(
        "/api/v1/decisions",
        headers={"Idempotency-Key": "reject-after-reset-test"},
        json={
            "recommendationId": snapshot["recommendationId"],
            "recommendationVersion": snapshot["recommendationVersion"],
            "action": "rejected",
            "comment": "Rejected after reopening.",
            "recommendationSnapshot": snapshot,
        },
    )
    assert rejected.status_code == 201
    assert rejected.json()["isActive"] is True
    assert db_session.query(RecommendationDecision).count() == 2
    db_session.refresh(stored)
    assert stored.status == "rejected"
