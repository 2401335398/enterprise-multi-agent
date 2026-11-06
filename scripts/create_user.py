"""Create a user account directly in the database.

Used to seed a demo environment when self-service registration is disabled.

Example:
    python scripts/create_user.py --email alice@example.com
"""

from __future__ import annotations

import argparse
import asyncio
import getpass

from app.auth.exceptions import EmailAlreadyRegistered
from app.auth.service import AuthService
from app.db.session import (
    async_session_factory,
    dispose_database_engine,
)


async def create_user(
    email: str,
    password: str,
    display_name: str | None,
) -> None:
    async with async_session_factory() as session:
        service = AuthService(session)
        user = await service.register(
            email=email,
            password=password,
            display_name=display_name,
        )
        print(f"Created user {user.email} ({user.id})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a user account.",
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Login email address.",
    )
    parser.add_argument(
        "--password",
        help="Password. Omit to be prompted without echo.",
    )
    parser.add_argument(
        "--display-name",
        default=None,
        help="Optional display name.",
    )
    args = parser.parse_args()

    password = args.password

    if not password:
        password = getpass.getpass("Password: ")

    async def run() -> None:
        try:
            await create_user(
                email=args.email,
                password=password,
                display_name=args.display_name,
            )
        except EmailAlreadyRegistered:
            print("A user with that email already exists.")
            raise SystemExit(1) from None
        except ValueError as exc:
            print(f"Invalid input: {exc}")
            raise SystemExit(1) from None
        finally:
            await dispose_database_engine()

    asyncio.run(run())


if __name__ == "__main__":
    main()
