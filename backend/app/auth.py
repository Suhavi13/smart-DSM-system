"""Local email/password authentication, session cookies, and role guards."""

from __future__ import annotations

import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from .database import get_db
from .models import AppUser


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")


def _required_setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required authentication setting: {name}")
    return value


APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
JWT_SECRET = _required_setting("AUTH_SECRET_KEY")
if len(JWT_SECRET) < 32:
    raise RuntimeError("AUTH_SECRET_KEY must contain at least 32 characters.")

JWT_ALGORITHM = "HS256"
JWT_ISSUER = os.getenv("AUTH_TOKEN_ISSUER", "gbtac-dsm-api").strip()
JWT_AUDIENCE = os.getenv("AUTH_TOKEN_AUDIENCE", "gbtac-dsm-frontend").strip()
ACCESS_TOKEN_MINUTES = max(5, int(os.getenv("AUTH_ACCESS_TOKEN_MINUTES", "480")))

AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "gbtac_session").strip()
CSRF_COOKIE_NAME = os.getenv("AUTH_CSRF_COOKIE_NAME", "gbtac_csrf").strip()
COOKIE_SECURE = os.getenv(
    "AUTH_COOKIE_SECURE",
    "true" if APP_ENV == "production" else "false",
).strip().lower() in {"1", "true", "yes", "on"}
COOKIE_SAMESITE = os.getenv(
    "AUTH_COOKIE_SAMESITE",
    "lax",
).strip().lower()
COOKIE_DOMAIN = os.getenv("AUTH_COOKIE_DOMAIN", "").strip() or None

if COOKIE_SAMESITE not in {"lax", "strict", "none"}:
    raise RuntimeError("AUTH_COOKIE_SAMESITE must be lax, strict, or none.")
if COOKIE_SAMESITE == "none" and not COOKIE_SECURE:
    raise RuntimeError("SameSite=None authentication cookies must also be Secure.")

MAX_FAILED_LOGINS = max(3, int(os.getenv("AUTH_MAX_FAILED_LOGINS", "5")))
LOCKOUT_MINUTES = max(1, int(os.getenv("AUTH_LOCKOUT_MINUTES", "15")))

password_hasher = PasswordHasher()
DUMMY_PASSWORD_HASH = password_hasher.hash(
    "This-is-only-a-timing-equalization-password-not-a-real-account"
)
UPPERCASE_PATTERN = re.compile(r"[A-Z]")
LOWERCASE_PATTERN = re.compile(r"[a-z]")
NUMBER_PATTERN = re.compile(r"\d")
SPECIAL_CHARACTER_PATTERN = re.compile(r"[^A-Za-z0-9\s]")
SPACE_PATTERN = re.compile(r"\s")
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


def normalize_email(email: str) -> str:
    normalized = email.strip().casefold()
    if (
        not normalized
        or len(normalized) > 320
        or "@" not in normalized
        or normalized.startswith("@")
        or normalized.endswith("@")
    ):
        raise ValueError("Enter a valid email address.")
    return normalized


def validate_role(role: str) -> str:
    normalized = role.strip().title()
    if normalized not in {"Viewer", "Operator"}:
        raise ValueError("Role must be Viewer or Operator.")
    return normalized


def validate_password(password: str) -> None:
    if len(password) < 8:
        raise ValueError("Passwords must contain at least 8 characters.")
    if len(password) > 1024:
        raise ValueError("Password is too long.")
    if not UPPERCASE_PATTERN.search(password):
        raise ValueError("Passwords must contain at least one uppercase letter.")
    if not LOWERCASE_PATTERN.search(password):
        raise ValueError("Passwords must contain at least one lowercase letter.")
    if not NUMBER_PATTERN.search(password):
        raise ValueError("Passwords must contain at least one number.")
    if not SPECIAL_CHARACTER_PATTERN.search(password):
        raise ValueError("Passwords must contain at least one special character.")
    if SPACE_PATTERN.search(password):
        raise ValueError("Passwords must not contain spaces.")


def hash_password(password: str) -> str:
    validate_password(password)
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def authenticate_user(db: Session, email: str, password: str) -> AppUser | None:
    try:
        normalized_email = normalize_email(email)
    except ValueError:
        normalized_email = "invalid@example.invalid"

    user = (
        db.query(AppUser)
        .filter(AppUser.email == normalized_email)
        .first()
    )

    # Always perform an Argon2 verification to reduce account-enumeration timing
    # differences, even when the email does not exist.
    password_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
    password_valid = verify_password(password, password_hash)

    if user is None:
        return None

    now = _utcnow()
    locked_until = _as_aware_utc(user.locked_until)
    if locked_until and locked_until > now:
        return None

    if not user.is_active or not password_valid:
        if user.is_active:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= MAX_FAILED_LOGINS:
                user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
                user.failed_login_attempts = 0
            db.commit()
        return None

    if password_hasher.check_needs_rehash(user.password_hash):
        user.password_hash = password_hasher.hash(password)

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    db.commit()
    db.refresh(user)
    return user


def create_access_token(user: AppUser) -> str:
    now = _utcnow()
    expires_at = now + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    claims = {
        "sub": str(user.user_id),
        "email": user.email,
        "ver": user.token_version,
        "iat": now,
        "nbf": now,
        "exp": expires_at,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _authentication_error(message: str = "Authentication is required.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _authorization_error(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)


def _cookie_options() -> dict:
    return {
        "secure": COOKIE_SECURE,
        "samesite": COOKIE_SAMESITE,
        "domain": COOKIE_DOMAIN,
        "path": "/",
    }


def issue_session(response: Response, user: AppUser) -> str:
    access_token = create_access_token(user)
    csrf_token = secrets.token_urlsafe(32)
    max_age = ACCESS_TOKEN_MINUTES * 60
    options = _cookie_options()

    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=access_token,
        max_age=max_age,
        httponly=True,
        **options,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=max_age,
        httponly=False,
        **options,
    )
    return csrf_token


def ensure_csrf_cookie(request: Request, response: Response) -> str:
    existing = request.cookies.get(CSRF_COOKIE_NAME)
    if existing:
        return existing

    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=ACCESS_TOKEN_MINUTES * 60,
        httponly=False,
        **_cookie_options(),
    )
    return csrf_token


def clear_session(response: Response) -> None:
    options = _cookie_options()
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        httponly=True,
        **options,
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        httponly=False,
        **options,
    )


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUser:
    token = None
    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    if not token:
        token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        raise _authentication_error()

    try:
        claims = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            options={"require": ["sub", "exp", "iat", "nbf", "iss", "aud", "ver"]},
        )
        user_id = int(claims["sub"])
        token_version = int(claims["ver"])
    except (InvalidTokenError, TypeError, ValueError, KeyError) as exc:
        raise _authentication_error("The session is invalid or expired.") from exc

    user = db.get(AppUser, user_id)
    if user is None or not user.is_active or user.token_version != token_version:
        raise _authentication_error("The account is unavailable or the session was revoked.")

    role = validate_role(user.role)
    return CurrentUser(
        object_id=str(user.user_id),
        tenant_id="local",
        name=user.display_name,
        username=user.email,
        roles=frozenset({role}),
        claims=claims,
    )


def require_csrf(request: Request) -> None:
    # Bearer-token API clients are not vulnerable to browser cookie CSRF.
    if request.headers.get("Authorization", "").lower().startswith("bearer "):
        return

    session_cookie = request.cookies.get(AUTH_COOKIE_NAME)
    if not session_cookie:
        return

    cookie_token = request.cookies.get(CSRF_COOKIE_NAME, "")
    header_token = request.headers.get("X-CSRF-Token", "")
    if not cookie_token or not header_token or not secrets.compare_digest(
        cookie_token,
        header_token,
    ):
        raise _authorization_error("The CSRF token is missing or invalid.")


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


def bootstrap_user_from_environment(db: Session) -> AppUser | None:
    email = os.getenv("BOOTSTRAP_USER_EMAIL", "").strip()
    if not email:
        return None

    normalized_email = normalize_email(email)
    existing = db.query(AppUser).filter(AppUser.email == normalized_email).first()
    if existing:
        return existing

    password = os.getenv("BOOTSTRAP_USER_PASSWORD", "")
    if not password:
        raise RuntimeError(
            "BOOTSTRAP_USER_PASSWORD is required when BOOTSTRAP_USER_EMAIL is set."
        )

    role = validate_role(os.getenv("BOOTSTRAP_USER_ROLE", "Operator"))
    display_name = (
        os.getenv("BOOTSTRAP_USER_NAME", "").strip()
        or normalized_email.split("@", 1)[0]
    )

    user = AppUser(
        email=normalized_email,
        display_name=display_name[:150],
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


viewer_or_operator = require_roles("Viewer", "Operator")
operator_only = require_roles("Operator")
