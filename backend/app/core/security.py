"""Security utilities: password hashing, JWT tokens.

No hardcoded secrets — all from Settings.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings

settings = get_settings()

ALGORITHM = "HS256"

# Access token: 24 hours — balanced between security and UX.
# Refresh token rotation provides the real long-lived auth.
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Refresh token: long-lived (7 days) — used to issue new access tokens
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Guest token: moderate lifetime (1 day)
GUEST_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    plain_bytes = plain_password.encode("utf-8")
    hash_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(plain_bytes, hash_bytes)


def get_password_hash(password: str) -> str:
    """Hash a password with bcrypt."""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def create_access_token(
    subject: str | Any,
    platform: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token.

    Args:
        subject: Usually the user ID (str or UUID).
        platform: The requesting platform (web, miniapp, ios, android).
        expires_delta: Custom expiration time.

    Returns:
        Encoded JWT string.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "access",
        "platform": platform or "unknown",
    }
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key.get_secret_value(), algorithm=ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(
    subject: str | Any,
    platform: str | None = None,
) -> str:
    """Create a JWT refresh token (long-lived, used only for /auth/refresh).

    Args:
        subject: Usually the user ID (str or UUID).
        platform: The requesting platform.

    Returns:
        Encoded JWT string.
    """
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh",
        "platform": platform or "unknown",
    }
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key.get_secret_value(), algorithm=ALGORITHM
    )
    return encoded_jwt


def create_guest_token(
    guest_session_id: str,
    fingerprint: str | None = None,
    platform: str | None = None,
) -> str:
    """Create a JWT token for guest sessions.

    Args:
        guest_session_id: The guest session UUID.
        fingerprint: Optional browser fingerprint.
        platform: The requesting platform.

    Returns:
        Encoded JWT string.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=GUEST_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "exp": expire,
        "sub": str(guest_session_id),
        "type": "guest",
        "fingerprint": fingerprint,
        "platform": platform or "unknown",
    }
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key.get_secret_value(), algorithm=ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: The JWT string.

    Returns:
        Decoded payload dict.

    Raises:
        jwt.ExpiredSignatureError: Token has expired.
        jwt.InvalidTokenError: Token is invalid.
    """
    payload = jwt.decode(
        token, settings.secret_key.get_secret_value(), algorithms=[ALGORITHM]
    )
    return payload
