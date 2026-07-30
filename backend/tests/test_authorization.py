from fastapi.testclient import TestClient

from backend.app.auth import CurrentUser, get_current_user
from backend.app.main import app


def _viewer() -> CurrentUser:
    return CurrentUser(
        object_id="viewer-oid",
        tenant_id="test-tenant-id",
        name="Test Viewer",
        username="viewer@example.com",
        roles=frozenset({"Viewer"}),
        claims={},
    )


def test_viewer_can_read_current_user(client: TestClient):
    app.dependency_overrides[get_current_user] = _viewer

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["isOperator"] is False
    assert response.json()["roles"] == ["Viewer"]


def test_viewer_cannot_create_decision(client: TestClient):
    app.dependency_overrides[get_current_user] = _viewer

    response = client.post(
        "/api/v1/decisions",
        headers={"Idempotency-Key": "viewer-test-key"},
        json={
            "recommendationId": "test-recommendation",
            "recommendationVersion": 1,
            "action": "approved",
            "comment": None,
            "recommendationSnapshot": {"title": "Test"},
        },
    )

    assert response.status_code == 403


def test_missing_token_returns_401():
    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.clear()

    try:
        with TestClient(app) as unauthenticated_client:
            response = unauthenticated_client.get("/api/v1/auth/me")
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)

    assert response.status_code == 401
