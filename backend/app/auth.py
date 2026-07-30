from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError, PyJWKClient, PyJWKClientError


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")


def _required_setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required Microsoft Entra setting: {name}")
    return value


TENANT_ID = _required_setting("ENTRA_TENANT_ID")
API_CLIENT_ID = _required_setting("ENTRA_API_CLIENT_ID")
SPA_CLIENT_ID = os.getenv("ENTRA_SPA_CLIENT_ID", "").strip()
REQUIRED_SCOPE = os.getenv("ENTRA_REQUIRED_SCOPE", "access_as_user").strip()

V2_ISSUER = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
V1_ISSUER = f"https://sts.windows.net/{TENANT_ID}/"
ALLOWED_ISSUERS = {V1_ISSUER, V2_ISSUER}
JWKS_URL = (
    f"https://login.microsoftonline.com/"
    f"{TENANT_ID}/discovery/v2.0/keys"
)

bearer_scheme = HTTPBearer(auto_error=False)
jwks_client = PyJWKClient(JWKS_URL)


@dataclass(frozen=True)
class CurrentUser:
    object_id: str
    tenant_id: str
    name: str
    username: str
    roles: frozenset[str]
    claims: dict


def _authentication_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _authorization_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=message,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _authentication_error("A Microsoft Entra access token is required.")

    token = credentials.credentials

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=[API_CLIENT_ID, f"api://{API_CLIENT_ID}"],
            options={
                "require": ["exp", "iss", "aud", "tid", "oid"],
            },
        )
    except (InvalidTokenError, PyJWKClientError) as exc:
        raise _authentication_error(
            "The Microsoft Entra access token is invalid or expired."
        ) from exc

    if claims.get("iss") not in ALLOWED_ISSUERS:
        raise _authentication_error("The access token issuer is not trusted.")

    if claims.get("ver") not in {"1.0", "2.0"}:
        raise _authentication_error("The Microsoft Entra token version is unsupported.")

    if claims.get("tid") != TENANT_ID:
        raise _authorization_error(
            "This account does not belong to the configured Microsoft Entra tenant."
        )

    # Restrict delegated access tokens to the dashboard SPA registration.
    calling_client_id = claims.get("azp") or claims.get("appid")
    if SPA_CLIENT_ID and calling_client_id != SPA_CLIENT_ID:
        raise _authorization_error(
            "The access token was issued to an unauthorized client application."
        )

    scopes = set(str(claims.get("scp", "")).split())
    if REQUIRED_SCOPE not in scopes:
        raise _authorization_error(
            f"The token does not contain the required scope: {REQUIRED_SCOPE}."
        )

    raw_roles = claims.get("roles", [])
    if isinstance(raw_roles, str):
        raw_roles = [raw_roles]

    roles = frozenset(str(role) for role in raw_roles)
    if not roles:
        raise _authorization_error(
            "No DSM application role has been assigned to this user."
        )

    return CurrentUser(
        object_id=str(claims["oid"]),
        tenant_id=str(claims["tid"]),
        name=str(claims.get("name", "Microsoft Entra user")),
        username=str(
            claims.get("preferred_username")
            or claims.get("upn")
            or claims["oid"]
        ),
        roles=roles,
        claims=claims,
    )


def require_roles(*allowed_roles: str) -> Callable:
    allowed = frozenset(allowed_roles)

    def dependency(
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if not user.roles.intersection(allowed):
            raise _authorization_error(
                "This action requires one of these roles: "
                f"{', '.join(sorted(allowed))}."
            )
        return user

    return dependency


viewer_or_operator = require_roles("Viewer", "Operator")
operator_only = require_roles("Operator")
