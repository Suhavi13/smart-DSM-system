"""Firebase Authentication token verification and role-based API guards."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

import firebase_admin
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from firebase_admin import exceptions as firebase_exceptions
from google.auth.exceptions import DefaultCredentialsError


FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "").strip()
FIREBASE_SERVICE_ACCOUNT_PATH = os.getenv(
    "FIREBASE_SERVICE_ACCOUNT_PATH", ""
).strip()
FIREBASE_CHECK_REVOKED_TOKENS = os.getenv(
    "FIREBASE_CHECK_REVOKED_TOKENS", "true"
).strip().lower() in {"1", "true", "yes", "on"}

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    object_id: str
    tenant_id: str
    name: str
    username: str
    roles: frozenset[str]
    claims: dict

    @property
    def email(self) -> str:
        return self.username


def validate_role(role: str) -> str:
    normalized = role.strip().title()
    if normalized not in {"Viewer", "Operator"}:
        raise ValueError("Role must be Viewer or Operator.")
    return normalized


def initialize_firebase_admin() -> firebase_admin.App:
    """Initialize one Firebase Admin app using server-side credentials only."""
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass

    if not FIREBASE_PROJECT_ID:
        raise RuntimeError(
            "FIREBASE_PROJECT_ID is required for Firebase Authentication."
        )

    options = {"projectId": FIREBASE_PROJECT_ID}
    if FIREBASE_SERVICE_ACCOUNT_PATH:
        credential = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_PATH)
        return firebase_admin.initialize_app(credential, options)

    # Application Default Credentials reads GOOGLE_APPLICATION_CREDENTIALS
    # locally and works automatically on supported Google Cloud environments.
    return firebase_admin.initialize_app(options=options)


def _authentication_error(message: str = "Authentication is required.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _authorization_error(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)


def _role_from_claims(claims: dict) -> str:
    claim = claims.get("role")
    if claim is None:
        # Self-service Firebase registrations start as Viewers. Only the Admin
        # SDK role-management script can add the Operator custom claim.
        return "Viewer"

    try:
        return validate_role(str(claim))
    except ValueError as exc:
        raise _authorization_error("The account has an invalid application role.") from exc


def get_current_user(
    credentials_value: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    if (
        credentials_value is None
        or credentials_value.scheme.lower() != "bearer"
        or not credentials_value.credentials
    ):
        raise _authentication_error()

    try:
        initialize_firebase_admin()
    except (DefaultCredentialsError, OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase Authentication is not configured on the API server.",
        ) from exc

    try:
        claims = firebase_auth.verify_id_token(
            credentials_value.credentials,
            check_revoked=FIREBASE_CHECK_REVOKED_TOKENS,
        )
    except firebase_auth.RevokedIdTokenError as exc:
        raise _authentication_error("The Firebase session was revoked. Sign in again.") from exc
    except firebase_auth.UserDisabledError as exc:
        raise _authentication_error("This Firebase account is disabled.") from exc
    except firebase_auth.ExpiredIdTokenError as exc:
        raise _authentication_error("The Firebase session expired. Sign in again.") from exc
    except firebase_auth.InvalidIdTokenError as exc:
        raise _authentication_error("The Firebase ID token is invalid.") from exc
    except firebase_auth.CertificateFetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase token verification is temporarily unavailable.",
        ) from exc
    except ValueError as exc:
        raise _authentication_error("The Firebase ID token is invalid.") from exc
    except (firebase_exceptions.FirebaseError, DefaultCredentialsError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase token verification is temporarily unavailable.",
        ) from exc

    uid = str(claims.get("uid") or claims.get("sub") or "").strip()
    email = str(claims.get("email") or "").strip().casefold()
    if not uid or not email:
        raise _authentication_error(
            "The Firebase account must contain a user ID and email address."
        )

    role = _role_from_claims(claims)
    display_name = str(claims.get("name") or "").strip()
    if not display_name:
        display_name = email.split("@", 1)[0]

    return CurrentUser(
        object_id=uid,
        tenant_id=FIREBASE_PROJECT_ID,
        name=display_name,
        username=email,
        roles=frozenset({role}),
        claims=claims,
    )


def require_roles(*allowed_roles: str) -> Callable:
    allowed = frozenset(validate_role(role) for role in allowed_roles)

    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.roles.intersection(allowed):
            raise _authorization_error(
                "This action requires one of these roles: "
                f"{', '.join(sorted(allowed))}."
            )
        return user

    return dependency


viewer_or_operator = require_roles("Viewer", "Operator")
operator_only = require_roles("Operator")
