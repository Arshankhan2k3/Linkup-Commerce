"""IAM dependency — JWT auth for protected routes.

Provides FastAPI dependencies:
- get_current_user_payload: decodes JWT, returns payload dict
- get_current_user_id: returns UUID of current user
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from modules.iam.application.services.token_service import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user_payload(
    token: str = Depends(oauth2_scheme),
) -> dict:
    """Decode and validate JWT. Returns the full payload dict."""
    try:
        payload = decode_access_token(token)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_id(
    payload: dict = Depends(get_current_user_payload),
) -> UUID:
    """Extract user UUID from JWT payload."""
    return UUID(payload["sub"])


async def get_current_store_id(
    payload: dict = Depends(get_current_user_payload),
) -> UUID:
    """Extract store UUID from JWT payload."""
    return UUID(payload["store_id"])


def require_permission(permission_code: str):
    """Dependency factory that checks a specific permission."""
    async def _check(payload: dict = Depends(get_current_user_payload)) -> dict:
        perms: list[str] = payload.get("permissions", [])
        if permission_code not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission_code}",
            )
        return payload
    return _check