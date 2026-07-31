"""Create and manage DSM Viewer/Operator accounts from the command line."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.auth import hash_password, normalize_email, validate_role
from backend.app.database import Base, SessionLocal, engine
from backend.app.models import AppUser


def prompt_password() -> str:
    password = getpass.getpass(
        "Password (8+ chars with uppercase, lowercase, number, special char, no spaces): "
    )
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise ValueError("Passwords do not match.")
    return password


def add_user(args: argparse.Namespace) -> None:
    email = normalize_email(args.email)
    role = validate_role(args.role)
    password = args.password or prompt_password()

    with SessionLocal() as db:
        if db.query(AppUser).filter(AppUser.email == email).first():
            raise ValueError(f"An account already exists for {email}.")

        user = AppUser(
            email=email,
            display_name=args.name.strip()[:150],
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"Created {role} account: {email}")


def set_role(args: argparse.Namespace) -> None:
    email = normalize_email(args.email)
    role = validate_role(args.role)
    with SessionLocal() as db:
        user = db.query(AppUser).filter(AppUser.email == email).first()
        if not user:
            raise ValueError(f"No account exists for {email}.")
        user.role = role
        user.token_version += 1
        db.commit()
        print(f"Updated {email} to {role}. Existing sessions were revoked.")


def reset_password(args: argparse.Namespace) -> None:
    email = normalize_email(args.email)
    password = args.password or prompt_password()
    with SessionLocal() as db:
        user = db.query(AppUser).filter(AppUser.email == email).first()
        if not user:
            raise ValueError(f"No account exists for {email}.")
        user.password_hash = hash_password(password)
        user.token_version += 1
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()
        print(f"Password reset for {email}. Existing sessions were revoked.")


def set_active(args: argparse.Namespace, active: bool) -> None:
    email = normalize_email(args.email)
    with SessionLocal() as db:
        user = db.query(AppUser).filter(AppUser.email == email).first()
        if not user:
            raise ValueError(f"No account exists for {email}.")
        user.is_active = active
        user.token_version += 1
        db.commit()
        state = "enabled" if active else "disabled"
        print(f"{email} is now {state}. Existing sessions were revoked.")


def list_users(_: argparse.Namespace) -> None:
    with SessionLocal() as db:
        users = db.query(AppUser).order_by(AppUser.email.asc()).all()
        if not users:
            print("No application users exist.")
            return
        for user in users:
            state = "active" if user.is_active else "disabled"
            print(f"{user.email:40} {user.role:8} {state}  {user.display_name}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    add = subparsers.add_parser("add", help="Create a Viewer or Operator")
    add.add_argument("--email", required=True)
    add.add_argument("--name", required=True)
    add.add_argument("--role", choices=["Viewer", "Operator"], required=True)
    add.add_argument("--password", help="Avoid this option in shared terminals.")
    add.set_defaults(handler=add_user)

    role = subparsers.add_parser("set-role", help="Change an account role")
    role.add_argument("--email", required=True)
    role.add_argument("--role", choices=["Viewer", "Operator"], required=True)
    role.set_defaults(handler=set_role)

    reset = subparsers.add_parser("reset-password", help="Reset a password")
    reset.add_argument("--email", required=True)
    reset.add_argument("--password", help="Avoid this option in shared terminals.")
    reset.set_defaults(handler=reset_password)

    disable = subparsers.add_parser("disable", help="Disable an account")
    disable.add_argument("--email", required=True)
    disable.set_defaults(handler=lambda args: set_active(args, False))

    enable = subparsers.add_parser("enable", help="Enable an account")
    enable.add_argument("--email", required=True)
    enable.set_defaults(handler=lambda args: set_active(args, True))

    listing = subparsers.add_parser("list", help="List configured accounts")
    listing.set_defaults(handler=list_users)
    return parser


def main() -> int:
    Base.metadata.create_all(bind=engine, tables=[AppUser.__table__])
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.handler(args)
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
