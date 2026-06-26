"""Authentication request/response schemas."""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import UserRole, UserStatus


def _validate_password_strength(v: str) -> str:
    """Password must be 8+ chars, contain at least one letter and one digit."""
    if len(v) < 8:
        raise ValueError("密码至少 8 个字符")
    if not re.search(r"[A-Za-z]", v):
        raise ValueError("密码需包含字母")
    if not re.search(r"\d", v):
        raise ValueError("密码需包含数字")
    return v


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    phone: str | None = Field(None, max_length=50)


class UserRegister(UserBase):
    """User registration request."""

    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)
    role: UserRole = UserRole.PATIENT
    license_number: str | None = Field(None, max_length=100)
    hospital: str | None = Field(None, max_length=255)
    department: str | None = Field(None, max_length=100)
    title: str | None = Field(None, max_length=50)


class UserLogin(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str | None = None
    type: str = "access"
    exp: datetime | None = None


class Token(BaseModel):
    """Token response."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int


class UserResponse(UserBase):
    """User response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: UserRole
    status: UserStatus
    is_verified: bool
    avatar_url: str | None
    license_number: str | None
    hospital: str | None
    department: str | None
    title: str | None
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None
    password_change_required: bool


class PasswordChangeRequest(BaseModel):
    """Password change request."""

    old_password: str | None = Field(None, min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def new_password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class UserUpdate(BaseModel):
    """Update user profile."""

    full_name: str | None = Field(None, min_length=1, max_length=255)
    phone: str | None = Field(None, max_length=50)
    avatar_url: str | None = Field(None, max_length=500)
    hospital: str | None = Field(None, max_length=255)
    department: str | None = Field(None, max_length=100)
    title: str | None = Field(None, max_length=50)
    license_number: str | None = Field(None, max_length=100)


class LoginResponse(Token):
    """Login response with user data."""

    user: UserResponse
    password_change_required: bool = False


class GuestSessionResponse(BaseModel):
    """Guest session response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_token: str
    message_count: int
    max_messages: int
    expires_at: datetime
    created_at: datetime


class RoleSwitchRequest(BaseModel):
    """Role switch request."""

    target_role: UserRole


class RoleSwitchResponse(BaseModel):
    """Role switch response."""

    new_token: str
    refresh_token: str | None = None
    previous_role: UserRole
    current_role: UserRole
    switched_at: datetime
