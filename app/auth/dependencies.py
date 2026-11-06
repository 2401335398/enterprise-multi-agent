from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.repository import UserRepository
from app.auth.service import AuthService
from app.db.models import UserModel
from app.db.session import get_db_session
from app.security.auth import Principal, require_principal


async def get_auth_service(
    db: AsyncSession = Depends(get_db_session),
) -> AuthService:
    return AuthService(db)


async def require_user(
    principal: Principal = Depends(require_principal),
    db: AsyncSession = Depends(get_db_session),
) -> UserModel:
    """
    Require a real user identity. Demo API keys and the dev local principal
    are not user accounts and therefore cannot access /api/auth/me.
    """

    if principal.auth_method != "jwt" or not principal.user_id:
        raise HTTPException(
            status_code=401,
            detail="User authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await UserRepository(db).get_by_id(
        principal.user_id
    )

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account is disabled.",
        )

    return user
