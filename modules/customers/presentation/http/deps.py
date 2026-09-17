"""Customers dependency — JWT auth for storefront customer routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from modules.iam.application.services.token_service import decode_access_token

customer_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/storefront/customers/login")


async def get_current_customer_payload(
    token: str = Depends(customer_oauth2_scheme),
) -> dict:
    """Decode and validate customer JWT token."""
    try:
        payload = decode_access_token(token)
        if payload.get("type") != "access" or payload.get("role") != "customer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid customer token type",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired customer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_customer_id(
    payload: dict = Depends(get_current_customer_payload),
) -> UUID:
    """Extract customer UUID from JWT payload."""
    return UUID(payload["sub"])
