"""CLI script to manage team access tokens for Impact Financial Document Processor.

Usage:
  python scripts/manage_tokens.py create "Alice Smith" --role reviewer
  python scripts/manage_tokens.py list
  python scripts/manage_tokens.py revoke "Alice Smith"
  python scripts/manage_tokens.py toggle "Alice Smith"
"""

import argparse
import secrets
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.config import Settings  # noqa: E402
from app.db import make_engine  # noqa: E402
from app.models import AccessToken, Base  # noqa: E402


def get_session():
    cfg = Settings()
    engine = make_engine(cfg.database_url.get_secret_value())
    Base.metadata.create_all(engine)
    return sessionmaker(engine)()


def generate_secure_token(name: str) -> str:
    slug = "".join(c.lower() if c.isalnum() else "_" for c in name).strip("_")[:12]
    random_part = secrets.token_urlsafe(24)
    return f"tok_{slug}_{random_part}"


def cmd_create(args):
    name = args.name.strip()
    if not name:
        print("[ERROR] Please provide a non-empty name.")
        sys.exit(1)

    session = get_session()
    with session:
        # Check if active token exists with same name
        existing = session.scalar(
            select(AccessToken).where(AccessToken.name == name, AccessToken.active.is_(True))
        )
        if existing and not args.force:
            print(f"[WARNING] An active token already exists for '{name}'.")
            print(f"Token: {existing.token}")
            print("Use --force to create an additional token anyway.")
            return

        token_str = generate_secure_token(name)
        token_obj = AccessToken(
            token=token_str,
            name=name,
            role=args.role,
            active=True,
        )
        session.add(token_obj)
        session.commit()

        print("=" * 65)
        print("  TEAM ACCESS TOKEN CREATED SUCCESSFULLY")
        print("=" * 65)
        print(f"  Team Member : {name}")
        print(f"  Role        : {args.role}")
        print(f"  Access Token: {token_str}")
        print("=" * 65)
        print("\nHow to give this to the team member:")
        print("  1. They can open the web app login page and paste this token.")
        print(f"     Their session will display as '{name}', and all their actions")
        print("     (confirming, editing, uploading, dismissing) will be recorded in their name.")
        print("  2. In API requests: Header 'Authorization: Bearer " + token_str + "'")
        print("-" * 65)


def cmd_list(args):
    session = get_session()
    with session:
        tokens = session.scalars(select(AccessToken).order_by(AccessToken.created_at.desc())).all()
        if not tokens:
            print(
                "No team access tokens found. Create one with: "
                "python scripts/manage_tokens.py create \"<Name>\""
            )
            return

        print("=" * 85)
        print(f"{'NAME':<20} | {'ROLE':<12} | {'STATUS':<8} | {'CREATED':<16} | {'TOKEN':<20}")
        print("-" * 85)
        for t in tokens:
            status = "ACTIVE" if t.active else "REVOKED"
            created = t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "—"
            masked_token = t.token[:14] + "..." + t.token[-6:] if len(t.token) > 24 else t.token
            print(f"{t.name:<20} | {t.role:<12} | {status:<8} | {created:<16} | {masked_token}")
        print("=" * 85)


def cmd_revoke(args):
    query_str = args.target.strip()
    session = get_session()
    with session:
        tokens = session.scalars(
            select(AccessToken).where(
                (AccessToken.name == query_str)
                | (AccessToken.token == query_str)
                | (AccessToken.id == query_str)
            )
        ).all()
        if not tokens:
            print(f"[ERROR] No token found matching '{query_str}'.")
            return

        for t in tokens:
            t.active = False
            print(f"[REVOKED] Deactivated token for '{t.name}' ({t.token[:12]}...).")
        session.commit()


def cmd_toggle(args):
    query_str = args.target.strip()
    session = get_session()
    with session:
        t = session.scalar(
            select(AccessToken).where(
                (AccessToken.name == query_str)
                | (AccessToken.token == query_str)
                | (AccessToken.id == query_str)
            )
        )
        if not t:
            print(f"[ERROR] No token found matching '{query_str}'.")
            return

        t.active = not t.active
        state = "ACTIVATED" if t.active else "DEACTIVATED"
        session.commit()
        print(f"[{state}] Token for '{t.name}' is now {state.lower()}.")


def main():
    parser = argparse.ArgumentParser(description="Manage team access tokens.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create
    p_create = subparsers.add_parser("create", help="Create a new access token for a team member.")
    p_create.add_argument("name", help="Name of team member (e.g. 'Sarah Connor')")
    p_create.add_argument("--role", default="reviewer", help="Role (default: reviewer)")
    p_create.add_argument(
        "--force", action="store_true", help="Create even if active token already exists"
    )
    p_create.set_defaults(func=cmd_create)

    # list
    p_list = subparsers.add_parser("list", help="List all access tokens.")
    p_list.set_defaults(func=cmd_list)

    # revoke
    p_revoke = subparsers.add_parser("revoke", help="Revoke access token by name or token string.")
    p_revoke.add_argument("target", help="Name, token string, or ID to revoke")
    p_revoke.set_defaults(func=cmd_revoke)

    # toggle
    p_toggle = subparsers.add_parser("toggle", help="Toggle active state of a token.")
    p_toggle.add_argument("target", help="Name, token string, or ID to toggle")
    p_toggle.set_defaults(func=cmd_toggle)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
