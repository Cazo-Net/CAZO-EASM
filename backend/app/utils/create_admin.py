"""Create (or promote) the platform admin account.

The account is a "superuser": it can sign in to the admin panel and see
platform-wide data. Its password is stored hashed in the users table, so it is
changed like any other user password (or by running this command again).

Usage:
    python -m app.utils.create_admin --email admin@example.com --password 's3cret'

Credentials may also be supplied via the ADMIN_EMAIL / ADMIN_PASSWORD
environment variables (useful for non-interactive deploys):
    ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=s3cret python -m app.utils.create_admin

The command is idempotent: if a user with the given email already exists it is
promoted to superuser (and reactivated) rather than duplicated.
"""
import argparse
import getpass
import os
import sys

from sqlalchemy import func

from app.database import SessionLocal, init_db
from app.core.security import get_password_hash
from app.models.user import User

MIN_PASSWORD_LENGTH = 12


def _resolve_credentials(args) -> tuple[str, str, str]:
    email = args.email or os.getenv("ADMIN_EMAIL")
    password = args.password or os.getenv("ADMIN_PASSWORD")
    full_name = args.full_name or os.getenv("ADMIN_FULL_NAME") or "Administrator"

    if not email:
        email = input("Admin email: ").strip()
    if not password:
        password = getpass.getpass("Admin password: ")

    email = (email or "").strip().lower()
    if not email or not password:
        print("Error: both email and password are required.", file=sys.stderr)
        sys.exit(2)
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"Error: the admin password must be at least {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
        sys.exit(2)

    return email, password, full_name


def create_admin(email: str, password: str, full_name: str) -> User:
    db = SessionLocal()
    try:
        user = db.query(User).filter(func.lower(User.email) == email.lower()).first()
        if user:
            user.role = "superuser"
            user.is_active = True
            user.email_verified = True
            user.hashed_password = get_password_hash(password)
            # Sign out any existing sessions that used the old password.
            user.token_version = (user.token_version or 0) + 1
            action = "updated"
        else:
            user = User(
                email=email,
                full_name=full_name,
                hashed_password=get_password_hash(password),
                role="superuser",
                is_active=True,
                email_verified=True,
            )
            db.add(user)
            action = "created"

        db.commit()
        db.refresh(user)
        print(f"Admin user {action}: {user.email} (id={user.id})")
        return user
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or promote the platform admin (superuser) account.")
    parser.add_argument("--email", help="Admin email (or set ADMIN_EMAIL)")
    parser.add_argument("--password", help="Admin password (or set ADMIN_PASSWORD)")
    parser.add_argument("--full-name", help="Admin full name (or set ADMIN_FULL_NAME)")
    args = parser.parse_args()

    init_db()
    email, password, full_name = _resolve_credentials(args)
    create_admin(email, password, full_name)


if __name__ == "__main__":
    main()
