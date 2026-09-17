"""JWT token service — access token creation and verification.

Access tokens: stateless JWT (short-lived, 30 min).
Refresh tokens: raw random strings stored HASHED in DB (handled by RefreshTokenRepository).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt

from app.core.config import settings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    *,
    user_id: UUID,
    store_id: UUID,
    staff_member_id: UUID | None = None,
    permissions: list[str],
) -> str:
    """Create a signed JWT access token for staff/admin users.

    Payload
    -------
    sub             : str(user_id)
    store_id        : str(store_id)
    staff_member_id : str(staff_member_id) if available
    permissions     : list of permission code strings
    type            : 'access'
    role            : 'staff'
    iat             : issued-at (UTC)
    exp             : expiry (UTC, settings.ACCESS_TOKEN_EXPIRE_MINUTES from now)
    """
    expire = _utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "store_id": str(store_id),
        "staff_member_id": str(staff_member_id) if staff_member_id else None,
        "permissions": permissions,
        "type": "access",
        "role": "staff",
        "iat": _utcnow(),
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_customer_access_token(
    *,
    customer_id: UUID,
    store_id: UUID,
) -> str:
    """Create a signed JWT access token for storefront customers.

    Payload
    -------
    sub         : str(customer_id)
    store_id    : str(store_id)
    type        : 'access'
    role        : 'customer'
    iat         : issued-at (UTC)
    exp         : expiry (UTC, settings.ACCESS_TOKEN_EXPIRE_MINUTES from now)
    """
    expire = _utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(customer_id),
        "store_id": str(store_id),
        "type": "access",
        "role": "customer",
        "iat": _utcnow(),
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
