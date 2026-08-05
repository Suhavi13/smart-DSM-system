"""Trusted Firebase user administration for Viewer/Operator access.

Examples:
  py backend/manage_users.py set-role --email person@example.com --role Operator
  py backend/manage_users.py set-role --email person@example.com --role Viewer
  py backend/manage_users.py disable --email person@example.com
  py backend/manage_users.py enable --email person@example.com
  py backend/manage_users.py list
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from firebase_admin import auth as firebase_auth

from backend.app.auth import initialize_firebase_admin, validate_role


def _find_user(args: argparse.Namespace):
    if getattr(args, "uid", None):
        return firebase_auth.get_user(args.uid)
    return firebase_auth.get_user_by_email(args.email.strip().casefold())


def set_role(args: argparse.Namespace) -> None:
    user = _find_user(args)
    role = validate_role(args.role)
    claims = dict(user.custom_claims or {})
    claims["role"] = role
    firebase_auth.set_custom_user_claims(user.uid, claims)
    firebase_auth.revoke_refresh_tokens(user.uid)
    print(
        f"Assigned {role} to {user.email}. Existing sessions were revoked; "
        "the user must sign in again."
    )


def set_disabled(args: argparse.Namespace, disabled: bool) -> None:
    user = _find_user(args)
    firebase_auth.update_user(user.uid, disabled=disabled)
    firebase_auth.revoke_refresh_tokens(user.uid)
    state = "disabled" if disabled else "enabled"
    print(f"{user.email} is now {state}.")


def list_users(_: argparse.Namespace) -> None:
    page = firebase_auth.list_users()
    while page:
        for user in page.users:
            claims = user.custom_claims or {}
            role = claims.get("role", "Viewer")
            state = "disabled" if user.disabled else "active"
            print(f"{(user.email or user.uid):45} {role:8} {state}")
        page = page.get_next_page()


def add_identity_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--email")
    group.add_argument("--uid")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Firebase DSM users")
    subparsers = parser.add_subparsers(dest="command", required=True)

    role_parser = subparsers.add_parser("set-role", help="Assign Viewer or Operator")
    add_identity_arguments(role_parser)
    role_parser.add_argument("--role", choices=["Viewer", "Operator"], required=True)
    role_parser.set_defaults(handler=set_role)

    disable_parser = subparsers.add_parser("disable", help="Disable a Firebase user")
    add_identity_arguments(disable_parser)
    disable_parser.set_defaults(handler=lambda args: set_disabled(args, True))

    enable_parser = subparsers.add_parser("enable", help="Enable a Firebase user")
    add_identity_arguments(enable_parser)
    enable_parser.set_defaults(handler=lambda args: set_disabled(args, False))

    list_parser = subparsers.add_parser("list", help="List Firebase users and roles")
    list_parser.set_defaults(handler=list_users)
    return parser


def main() -> None:
    initialize_firebase_admin()
    args = build_parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
