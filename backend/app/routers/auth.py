"""Authentication routes for signup, login, logout, and current user lookup."""

from __future__ import annotations

import os
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.auth import (
    CurrentUser,
    authenticate_user,
    clear_session,
    ensure_csrf_cookie,
    hash_password,
    issue_session,
    normalize_email,
    require_csrf,
    viewer_or_operator,
)
from backend.app.database import get_db
from backend.app.models import AppUser


router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

PUBLIC_VIEWER_SIGNUP_ENABLED = os.getenv(
    "PUBLIC_VIEWER_SIGNUP_ENABLED", "true"
).strip().lower() in {"1", "true", "yes", "on"}
SIGNUP_MAX_PER_HOUR = max(1, int(os.getenv("AUTH_SIGNUP_MAX_PER_HOUR", "10")))
TRUST_PROXY_HEADERS = os.getenv(
    "TRUST_PROXY_HEADERS", "false"
).strip().lower() in {"1", "true", "yes", "on"}

_signup_attempts: dict[str, deque[datetime]] = defaultdict(deque)
_signup_lock = Lock()


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class SignupRequest(BaseModel):
    # A caller cannot include role/isOperator fields and elevate itself.
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(alias="displayName", min_length=1, max_length=150)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=1024)


def _serialize_user(user: CurrentUser, csrf_token: str) -> dict:
    return {
        "objectId": user.object_id,
        "name": user.name,
        "username": user.username,
        "email": user.username,
        "roles": sorted(user.roles),
        "isOperator": "Operator" in user.roles,
        "csrfToken": csrf_token,
    }


def _current_user_from_record(user_record: AppUser) -> CurrentUser:
    return CurrentUser(
        object_id=str(user_record.user_id),
        tenant_id="local",
        name=user_record.display_name,
        username=user_record.email,
        roles=frozenset({user_record.role}),
        claims={},
    )


def _client_identifier(request: Request) -> str:
    if TRUST_PROXY_HEADERS:
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()[:100]
    if request.client and request.client.host:
        return request.client.host[:100]
    return "unknown"


def _enforce_signup_rate_limit(request: Request) -> None:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=1)
    client_id = _client_identifier(request)

    with _signup_lock:
        attempts = _signup_attempts[client_id]
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        if len(attempts) >= SIGNUP_MAX_PER_HOUR:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many accounts were created from this connection. Try again later.",
                headers={"Retry-After": "3600"},
            )
        attempts.append(now)


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup_viewer(
    payload: SignupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    """Create a self-service Viewer account and sign it in.

    The role is deliberately hard-coded on the server. Operator access can only
    be granted later through a trusted database/admin action.
    """
    if not PUBLIC_VIEWER_SIGNUP_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Public account creation is disabled.",
        )

    _enforce_signup_rate_limit(request)

    try:
        email = normalize_email(payload.email)
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    display_name = " ".join(payload.display_name.strip().split())
    if not display_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enter your name.",
        )

    user_record = AppUser(
        email=email,
        display_name=display_name[:150],
        password_hash=password_hash,
        role="Viewer",
        is_active=True,
    )
    db.add(user_record)

    try:
        db.commit()
        db.refresh(user_record)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account already exists for this email. Sign in instead.",
        ) from exc

    csrf_token = issue_session(response, user_record)
    return _serialize_user(_current_user_from_record(user_record), csrf_token)


@router.post("/login")
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    user_record = authenticate_user(db, payload.email, payload.password)
    if user_record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    csrf_token = issue_session(response, user_record)
    return _serialize_user(_current_user_from_record(user_record), csrf_token)


@router.get("/me")
def get_authenticated_user(
    request: Request,
    response: Response,
    user: CurrentUser = Depends(viewer_or_operator),
) -> dict:
    csrf_token = ensure_csrf_cookie(request, response)
    return _serialize_user(user, csrf_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    _: None = Depends(require_csrf),
) -> Response:
    clear_session(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
