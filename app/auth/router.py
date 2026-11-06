from __future__ import annotations

from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)

from app.auth.dependencies import (
    get_auth_service,
    require_user,
)
from app.auth.exceptions import (
    AuthError,
    EmailAlreadyRegistered,
    InactiveUser,
    InvalidCredentials,
    InvalidRefreshToken,
    RefreshTokenReuseDetected,
    RegistrationDisabled,
)
from app.auth.schemas import (
    LoginRequest,
    RefreshResponse,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.auth.service import AuthService
from app.auth.tokens import refresh_token_max_age_seconds
from app.core.config import settings
from app.db.models import UserModel


router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_PATH = "/api/auth"


# ============================================================
# Helpers
# ============================================================

def _auth_http_exception(exc: AuthError) -> HTTPException:
    if isinstance(exc, EmailAlreadyRegistered):
        return HTTPException(
            status_code=409,
            detail="Email already registered.",
        )

    if isinstance(exc, InvalidCredentials):
        return HTTPException(
            status_code=401,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if isinstance(exc, InactiveUser):
        return HTTPException(
            status_code=403,
            detail="Account is disabled.",
        )

    if isinstance(exc, RefreshTokenReuseDetected):
        return HTTPException(
            status_code=401,
            detail=(
                "Refresh token reuse detected. "
                "Please log in again."
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )

    if isinstance(exc, InvalidRefreshToken):
        detail = str(exc) or "Invalid or expired refresh token."
        return HTTPException(
            status_code=401,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if isinstance(exc, RegistrationDisabled):
        return HTTPException(
            status_code=403,
            detail="Registration is disabled.",
        )

    return HTTPException(
        status_code=401,
        detail="Authentication failed.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _client_metadata(
    request: Request,
) -> tuple[str | None, str | None]:
    user_agent = request.headers.get("user-agent")
    ip_address = request.headers.get("x-real-ip")

    if not ip_address and request.client is not None:
        ip_address = request.client.host

    return user_agent, ip_address


def _set_refresh_cookie(
    response: Response,
    raw_refresh_token: str,
    expires_at: datetime,
) -> None:
    response.set_cookie(
        key=settings.refresh_token_cookie_name,
        value=raw_refresh_token,
        max_age=refresh_token_max_age_seconds(),
        expires=expires_at,
        path=REFRESH_COOKIE_PATH,
        secure=settings.refresh_token_cookie_secure,
        httponly=True,
        samesite=settings.refresh_token_cookie_samesite,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_token_cookie_name,
        path=REFRESH_COOKIE_PATH,
    )


def _deliver_refresh_token(
    response: Response,
    raw_refresh_token: str,
    expires_at: datetime,
) -> str | None:
    if settings.refresh_token_delivery == "body":
        return raw_refresh_token

    _set_refresh_cookie(
        response,
        raw_refresh_token,
        expires_at,
    )
    return None


def _extract_refresh_token(
    request: Request,
    payload: RefreshTokenRequest | None,
) -> str | None:
    cooked = request.cookies.get(
        settings.refresh_token_cookie_name
    )

    if cooked:
        return cooked

    if payload is not None and payload.refresh_token is not None:
        return payload.refresh_token.get_secret_value()

    return None


# ============================================================
# Endpoints
# ============================================================

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    if not settings.registration_enabled:
        raise _auth_http_exception(RegistrationDisabled())

    try:
        user = await service.register(
            email=str(payload.email),
            password=payload.password.get_secret_value(),
            display_name=payload.display_name,
        )
    except AuthError as exc:
        raise _auth_http_exception(exc) from exc

    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    response_model_exclude_none=True,
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    user_agent, ip_address = _client_metadata(request)

    try:
        user, issued = await service.authenticate(
            email=str(payload.email),
            password=payload.password.get_secret_value(),
            user_agent=user_agent,
            ip_address=ip_address,
        )
    except AuthError as exc:
        raise _auth_http_exception(exc) from exc

    refresh_token = _deliver_refresh_token(
        response,
        issued.refresh_token,
        issued.refresh_expires_at,
    )

    return TokenResponse(
        access_token=issued.access_token,
        expires_in=issued.expires_in,
        user=UserResponse.model_validate(user),
        refresh_token=refresh_token,
    )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    response_model_exclude_none=True,
)
async def refresh(
    request: Request,
    response: Response,
    payload: RefreshTokenRequest | None = None,
    service: AuthService = Depends(get_auth_service),
) -> RefreshResponse:
    raw_refresh_token = _extract_refresh_token(
        request,
        payload,
    )

    if not raw_refresh_token:
        raise HTTPException(
            status_code=401,
            detail="Missing refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_agent, ip_address = _client_metadata(request)

    try:
        _, issued = await service.refresh(
            raw_refresh_token,
            user_agent=user_agent,
            ip_address=ip_address,
        )
    except AuthError as exc:
        raise _auth_http_exception(exc) from exc

    refresh_token = _deliver_refresh_token(
        response,
        issued.refresh_token,
        issued.refresh_expires_at,
    )

    return RefreshResponse(
        access_token=issued.access_token,
        expires_in=issued.expires_in,
        refresh_token=refresh_token,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def logout(
    request: Request,
    response: Response,
    payload: RefreshTokenRequest | None = None,
    service: AuthService = Depends(get_auth_service),
) -> None:
    raw_refresh_token = _extract_refresh_token(
        request,
        payload,
    )

    if raw_refresh_token:
        await service.logout(raw_refresh_token)

    _clear_refresh_cookie(response)
    return None


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def logout_all(
    response: Response,
    user: UserModel = Depends(require_user),
    service: AuthService = Depends(get_auth_service),
) -> None:
    user_id = user.id
    await service.logout_all(user_id)
    _clear_refresh_cookie(response)
    return None


@router.get(
    "/me",
    response_model=UserResponse,
)
async def me(
    user: UserModel = Depends(require_user),
) -> UserResponse:
    return UserResponse.model_validate(user)
