from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.exceptions import (
    EmailAlreadyRegistered,
    InactiveUser,
    InvalidCredentials,
    InvalidRefreshToken,
    RefreshTokenReuseDetected,
)
from app.auth.jwt import create_access_token
from app.auth.passwords import (
    dummy_password_hash,
    hash_password,
    validate_password_policy,
    verify_and_update_password,
    verify_password,
)
from app.auth.repository import (
    RefreshTokenRepository,
    UserRepository,
)
from app.auth.tokens import (
    generate_refresh_token,
    hash_refresh_token,
    refresh_token_expires_at,
    utcnow,
)
from app.core.config import settings
from app.db.models import RefreshTokenModel, UserModel


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _clip(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    return value[:limit]


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_expires_at: datetime


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)

    # ========================================================
    # Registration
    # ========================================================

    async def register(
        self,
        email: str,
        password: str,
        display_name: str | None = None,
    ) -> UserModel:
        email = normalize_email(email)
        validate_password_policy(password)

        existing = await self.users.get_by_email(email)
        if existing is not None:
            raise EmailAlreadyRegistered()

        display_name = (display_name or "").strip()
        if not display_name:
            display_name = email.split("@", 1)[0]

        user = UserModel(
            email=email,
            password_hash=hash_password(password),
            display_name=display_name[:100],
            is_active=True,
        )
        self.users.add(user)

        try:
            await self.session.commit()
        except IntegrityError as exc:
            # Covers the race where another request inserted the same email
            # after our existence check.
            await self.session.rollback()
            raise EmailAlreadyRegistered() from exc

        await self.session.refresh(user)
        return user

    # ========================================================
    # Login
    # ========================================================

    async def authenticate(
        self,
        email: str,
        password: str,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[UserModel, IssuedTokens]:
        email = normalize_email(email)
        user = await self.users.get_by_email(email)

        if user is None:
            # Keep the response time close to the known-email path.
            verify_password(password, dummy_password_hash())
            raise InvalidCredentials()

        valid, new_hash = verify_and_update_password(
            password,
            user.password_hash,
        )

        if not valid:
            raise InvalidCredentials()

        if new_hash is not None:
            self.users.set_password_hash(user, new_hash)

        if not user.is_active:
            raise InactiveUser()

        now = utcnow()
        self.users.set_last_login(user, now)

        issued = self._issue_tokens(
            user,
            family_id=uuid.uuid4(),
            issued_at=now,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        await self.session.commit()
        return user, issued

    # ========================================================
    # Refresh
    # ========================================================

    async def refresh(
        self,
        raw_refresh_token: str,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[UserModel, IssuedTokens]:
        token_hash = hash_refresh_token(raw_refresh_token)
        now = utcnow()

        stored = await self.refresh_tokens.get_by_hash_for_update(
            token_hash
        )

        if stored is None:
            raise InvalidRefreshToken()

        if stored.expires_at <= now:
            raise InvalidRefreshToken()

        if stored.revoked_at is not None:
            grace = timedelta(
                seconds=settings.refresh_token_reuse_grace_seconds
            )

            # Two tabs refreshing at the same time is a normal race, not
            # theft. Reject the second request, but do not destroy the
            # freshly rotated family.
            if (
                stored.revoked_reason == "rotated"
                and stored.replaced_by_id is not None
                and stored.revoked_at >= now - grace
            ):
                raise InvalidRefreshToken(
                    "Refresh token has already been used."
                )

            # Confirmed reuse: revoke the whole family and invalidate
            # outstanding access tokens as well.
            await self.refresh_tokens.revoke_family(
                stored.family_id,
                reason="reuse_detected",
                revoked_at=now,
            )
            await self.users.increment_token_version(
                stored.user_id
            )
            await self.session.commit()
            raise RefreshTokenReuseDetected()

        user = await self.users.get_by_id(stored.user_id)

        if user is None:
            await self.session.rollback()
            raise InvalidRefreshToken()

        if not user.is_active:
            await self.refresh_tokens.revoke_family(
                stored.family_id,
                reason="inactive_user",
                revoked_at=now,
            )
            await self.session.commit()
            raise InactiveUser()

        new_token_id = uuid.uuid4()
        new_raw_token = generate_refresh_token()
        new_expires_at = refresh_token_expires_at(now)

        new_token = RefreshTokenModel(
            id=new_token_id,
            user_id=user.id,
            token_hash=hash_refresh_token(new_raw_token),
            family_id=stored.family_id,
            expires_at=new_expires_at,
            user_agent=_clip(user_agent, 512),
            ip_address=_clip(ip_address, 45),
        )
        self.refresh_tokens.add(new_token)
        self.refresh_tokens.revoke(
            stored,
            reason="rotated",
            replaced_by_id=new_token_id,
            revoked_at=now,
        )

        await self.session.commit()

        return user, IssuedTokens(
            access_token=create_access_token(
                str(user.id),
                user.token_version,
            ),
            refresh_token=new_raw_token,
            expires_in=settings.access_token_ttl_seconds,
            refresh_expires_at=new_expires_at,
        )

    # ========================================================
    # Logout
    # ========================================================

    async def logout(
        self,
        raw_refresh_token: str | None,
    ) -> None:
        if not raw_refresh_token:
            return

        stored = await self.refresh_tokens.get_by_hash_for_update(
            hash_refresh_token(raw_refresh_token)
        )

        if stored is None:
            return

        # Revoke the family rather than only this row: if a rotation just
        # produced a successor, logout must kill that successor too.
        await self.refresh_tokens.revoke_family(
            stored.family_id,
            reason="logout",
        )
        await self.session.commit()

    async def logout_all(self, user_id: uuid.UUID | str) -> None:
        await self.users.increment_token_version(user_id)
        await self.refresh_tokens.revoke_all_for_user(
            user_id,
            reason="logout_all",
        )
        await self.session.commit()

    # ========================================================
    # Helpers
    # ========================================================

    async def get_user(
        self,
        user_id: uuid.UUID | str,
    ) -> UserModel | None:
        return await self.users.get_by_id(user_id)

    def _issue_tokens(
        self,
        user: UserModel,
        *,
        family_id: uuid.UUID,
        issued_at: datetime,
        user_agent: str | None,
        ip_address: str | None,
    ) -> IssuedTokens:
        raw_refresh_token = generate_refresh_token()
        refresh_expires_at = refresh_token_expires_at(issued_at)

        token = RefreshTokenModel(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh_token),
            family_id=family_id,
            expires_at=refresh_expires_at,
            user_agent=_clip(user_agent, 512),
            ip_address=_clip(ip_address, 45),
        )
        self.refresh_tokens.add(token)

        return IssuedTokens(
            access_token=create_access_token(
                str(user.id),
                user.token_version,
            ),
            refresh_token=raw_refresh_token,
            expires_in=settings.access_token_ttl_seconds,
            refresh_expires_at=refresh_expires_at,
        )
