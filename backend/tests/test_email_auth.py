"""Email/password signup and login endpoint tests."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user, hash_password
from backend.app.main import app
from backend.app.models import AppUser


VALID_PASSWORD = "Correct-horse-battery-staple1!"
SIGNUP_PASSWORD = "Viewer-created-password1!"


def create_user(db: Session, *, email: str, role: str) -> AppUser:
    user = AppUser(
        email=email,
        display_name="Test User",
        password_hash=hash_password(VALID_PASSWORD),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_login_sets_session_and_returns_server_role(
    client: TestClient,
    db_session: Session,
):
    create_user(db_session, email="viewer@example.com", role="Viewer")

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "VIEWER@example.com",
            "password": VALID_PASSWORD,
        },
    )

    assert response.status_code == 200
    assert response.json()["roles"] == ["Viewer"]
    assert response.json()["isOperator"] is False
    assert "gbtac_session=" in response.headers["set-cookie"]


def test_wrong_password_is_rejected(client: TestClient, db_session: Session):
    create_user(db_session, email="operator@example.com", role="Operator")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "operator@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_cookie_session_can_read_me(client: TestClient, db_session: Session):
    create_user(db_session, email="operator@example.com", role="Operator")
    original_override = app.dependency_overrides.pop(get_current_user, None)
    try:
        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": "operator@example.com",
                "password": VALID_PASSWORD,
            },
        )
        assert login.status_code == 200

        response = client.get("/api/v1/auth/me")
    finally:
        if original_override is not None:
            app.dependency_overrides[get_current_user] = original_override

    assert response.status_code == 200
    assert response.json()["isOperator"] is True
    assert response.json()["username"] == "operator@example.com"


def test_cookie_decision_requires_csrf(client: TestClient, db_session: Session):
    create_user(db_session, email="operator@example.com", role="Operator")
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "operator@example.com",
            "password": VALID_PASSWORD,
        },
    )
    assert login.status_code == 200

    response = client.post(
        "/api/v1/decisions",
        headers={"Idempotency-Key": "missing-csrf-test"},
        json={
            "recommendationId": "csrf-test",
            "recommendationVersion": 1,
            "action": "approved",
            "comment": None,
            "recommendationSnapshot": {"title": "Test"},
        },
    )

    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]


def test_public_signup_creates_viewer_and_signs_in(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "displayName": "New Viewer",
            "email": "NEW.VIEWER@example.com",
            "password": SIGNUP_PASSWORD,
        },
    )

    assert response.status_code == 201
    assert response.json()["roles"] == ["Viewer"]
    assert response.json()["isOperator"] is False
    assert "gbtac_session=" in response.headers["set-cookie"]

    saved = db_session.query(AppUser).filter(
        AppUser.email == "new.viewer@example.com"
    ).one()
    assert saved.role == "Viewer"
    assert saved.password_hash != SIGNUP_PASSWORD


def test_signup_rejects_password_without_special_character(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "displayName": "Weak Password",
            "email": "weak-password@example.com",
            "password": "Password123",
        },
    )

    assert response.status_code == 422
    assert "special character" in response.json()["detail"]
    assert db_session.query(AppUser).filter(
        AppUser.email == "weak-password@example.com"
    ).first() is None


def test_signup_cannot_choose_operator_role(
    client: TestClient,
    db_session: Session,
):
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "displayName": "Role Attacker",
            "email": "attacker@example.com",
            "password": SIGNUP_PASSWORD,
            "role": "Operator",
        },
    )

    assert response.status_code == 422
    assert db_session.query(AppUser).filter(
        AppUser.email == "attacker@example.com"
    ).first() is None


def test_duplicate_signup_is_rejected(
    client: TestClient,
    db_session: Session,
):
    create_user(db_session, email="existing@example.com", role="Viewer")

    response = client.post(
        "/api/v1/auth/signup",
        json={
            "displayName": "Existing Viewer",
            "email": "existing@example.com",
            "password": SIGNUP_PASSWORD,
        },
    )

    assert response.status_code == 409
