"""Firebase ID-token verification and application-role tests."""

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from backend.app import auth as auth_module


def _credentials() -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials="firebase-token")


def _verified_claims(**overrides) -> dict:
    claims = {
        "uid": "firebase-uid-123",
        "sub": "firebase-uid-123",
        "email": "person@example.com",
        "name": "Firebase Person",
    }
    claims.update(overrides)
    return claims


def test_firebase_user_without_role_defaults_to_viewer(monkeypatch):
    monkeypatch.setattr(auth_module, "initialize_firebase_admin", lambda: None)
    monkeypatch.setattr(
        auth_module.firebase_auth,
        "verify_id_token",
        lambda token, check_revoked: _verified_claims(),
    )

    user = auth_module.get_current_user(_credentials())

    assert user.object_id == "firebase-uid-123"
    assert user.email == "person@example.com"
    assert user.roles == frozenset({"Viewer"})


def test_operator_custom_claim_is_trusted_after_token_verification(monkeypatch):
    monkeypatch.setattr(auth_module, "initialize_firebase_admin", lambda: None)
    monkeypatch.setattr(
        auth_module.firebase_auth,
        "verify_id_token",
        lambda token, check_revoked: _verified_claims(role="Operator"),
    )

    user = auth_module.get_current_user(_credentials())

    assert user.roles == frozenset({"Operator"})


def test_invalid_custom_claim_role_is_rejected(monkeypatch):
    monkeypatch.setattr(auth_module, "initialize_firebase_admin", lambda: None)
    monkeypatch.setattr(
        auth_module.firebase_auth,
        "verify_id_token",
        lambda token, check_revoked: _verified_claims(role="Administrator"),
    )

    with pytest.raises(HTTPException) as exc_info:
        auth_module.get_current_user(_credentials())

    assert exc_info.value.status_code == 403


def test_missing_bearer_token_is_rejected():
    with pytest.raises(HTTPException) as exc_info:
        auth_module.get_current_user(None)

    assert exc_info.value.status_code == 401


def test_verified_token_requires_email(monkeypatch):
    monkeypatch.setattr(auth_module, "initialize_firebase_admin", lambda: None)
    monkeypatch.setattr(
        auth_module.firebase_auth,
        "verify_id_token",
        lambda token, check_revoked: _verified_claims(email=""),
    )

    with pytest.raises(HTTPException) as exc_info:
        auth_module.get_current_user(_credentials())

    assert exc_info.value.status_code == 401
