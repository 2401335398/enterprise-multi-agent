from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
)

from app.auth.passwords import validate_password_policy


class RegisterRequest(BaseModel):
    email: EmailStr
    password: SecretStr
    display_name: str | None = Field(default=None, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: SecretStr) -> SecretStr:
        validate_password_policy(value.get_secret_value())
        return value

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()
        return value or None


class LoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr


class RefreshTokenRequest(BaseModel):
    refresh_token: SecretStr | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str
    is_active: bool
    email_verified_at: datetime | None = None
    created_at: datetime
    last_login_at: datetime | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
    refresh_token: str | None = None


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str | None = None
