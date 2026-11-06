import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import utcnow
from app.db.models import RefreshTokenModel, UserModel


def _parse_uuid(value: uuid.UUID | str) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value

    try:
        return uuid.UUID(value)
    except (TypeError, ValueError, AttributeError):
        return None


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> UserModel | None:
        statement = select(UserModel).where(
            UserModel.email == email
        )
        return await self.session.scalar(statement)

    async def get_by_id(
        self,
        user_id: uuid.UUID | str,
    ) -> UserModel | None:
        parsed_id = _parse_uuid(user_id)
        if parsed_id is None:
            return None
        return await self.session.get(UserModel, parsed_id)

    def add(self, user: UserModel) -> None:
        self.session.add(user)

    def set_password_hash(
        self,
        user: UserModel,
        password_hash: str,
    ) -> None:
        user.password_hash = password_hash

    def set_last_login(
        self,
        user: UserModel,
        logged_in_at: datetime,
    ) -> None:
        user.last_login_at = logged_in_at

    async def increment_token_version(
        self,
        user_id: uuid.UUID | str,
    ) -> int:
        parsed_id = _parse_uuid(user_id)
        if parsed_id is None:
            return 0

        statement = (
            update(UserModel)
            .where(UserModel.id == parsed_id)
            .values(
                token_version=UserModel.token_version + 1
            )
            .execution_options(synchronize_session=False)
        )
        result = await self.session.execute(statement)
        return int(result.rowcount or 0)


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, token: RefreshTokenModel) -> None:
        self.session.add(token)

    async def get_by_hash(
        self,
        token_hash: str,
    ) -> RefreshTokenModel | None:
        statement = select(RefreshTokenModel).where(
            RefreshTokenModel.token_hash == token_hash
        )
        return await self.session.scalar(statement)

    async def get_by_hash_for_update(
        self,
        token_hash: str,
    ) -> RefreshTokenModel | None:
        statement = (
            select(RefreshTokenModel)
            .where(RefreshTokenModel.token_hash == token_hash)
            .with_for_update()
        )
        return await self.session.scalar(statement)

    def revoke(
        self,
        token: RefreshTokenModel,
        *,
        reason: str,
        replaced_by_id: uuid.UUID | None = None,
        revoked_at: datetime | None = None,
    ) -> None:
        token.revoked_at = revoked_at or utcnow()
        token.revoked_reason = reason
        token.replaced_by_id = replaced_by_id

    async def revoke_family(
        self,
        family_id: uuid.UUID,
        *,
        reason: str,
        revoked_at: datetime | None = None,
    ) -> int:
        statement = (
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.family_id == family_id,
                RefreshTokenModel.revoked_at.is_(None),
            )
            .values(
                revoked_at=revoked_at or utcnow(),
                revoked_reason=reason,
            )
            .execution_options(synchronize_session=False)
        )
        result = await self.session.execute(statement)
        return int(result.rowcount or 0)

    async def revoke_all_for_user(
        self,
        user_id: uuid.UUID | str,
        *,
        reason: str,
        revoked_at: datetime | None = None,
    ) -> int:
        parsed_id = _parse_uuid(user_id)
        if parsed_id is None:
            return 0

        statement = (
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.user_id == parsed_id,
                RefreshTokenModel.revoked_at.is_(None),
            )
            .values(
                revoked_at=revoked_at or utcnow(),
                revoked_reason=reason,
            )
            .execution_options(synchronize_session=False)
        )
        result = await self.session.execute(statement)
        return int(result.rowcount or 0)
