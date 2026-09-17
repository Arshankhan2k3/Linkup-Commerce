"""Login user command — verifies credentials, creates token pair.

Refresh tokens are stored HASHED in the DB with a family_id.
The caller must call uow.commit() — this handler does NOT commit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.core.security import verify_password
from modules.iam.application.services.token_service import create_access_token
from modules.iam.infrastructure.db.models import RefreshTokenModel
from modules.iam.infrastructure.db.repository import (
    RefreshTokenRepository,
    StaffMemberRepository,
    UserRepository,
)
from shared.domain.exceptions import UnauthorizedActionError
from shared.domain.ids import generate_uuid


@dataclass
class LoginResult:
    access_token: str
    refresh_token_raw: str   # raw token — only returned once, never stored
    user_id: UUID
    store_id: UUID
    staff_member_id: UUID | None = None
    permissions: list[str] = field(default_factory=list)


async def login_user(
    *,
    user_repo: UserRepository,
    staff_repo: StaffMemberRepository,
    refresh_repo: RefreshTokenRepository,
    store_id: UUID,
    email: str,
    password: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> LoginResult:
    """Authenticate and return an access + refresh token pair.

    Raises
    ------
    UnauthorizedActionError : invalid credentials or inactive user.
    """
    user = await user_repo.get_by_email(email=email)

    if user is None or not verify_password(password, user.password_hash):
        raise UnauthorizedActionError("Invalid email or password")

    if user.status != "ACTIVE":
        raise UnauthorizedActionError("User account is inactive or locked")

    # Verify staff membership for this store
    staff = await staff_repo.get_by_user_and_store(user.user_id, store_id)
    if staff is None or staff.status != "ACTIVE":
        raise UnauthorizedActionError("Staff membership is inactive or not found for this store")

    # Collect permissions via staff member → roles → permissions
    permissions = await staff_repo.get_permission_codes(staff.staff_member_id)

    # Create access token (JWT, stateless)
    access_token = create_access_token(
        user_id=user.user_id,
        store_id=store_id,
        staff_member_id=staff.staff_member_id,
        permissions=permissions,
    )

    # Create refresh token (stored hashed in DB)
    raw_token = refresh_repo.generate_raw()
    token_hash = refresh_repo.hash_token(raw_token)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    device_info: dict[str, Any] = {}
    if user_agent:
        device_info["user_agent"] = user_agent

    refresh = RefreshTokenModel(
        token_id=generate_uuid(),
        user_id=user.user_id,
        family_id=generate_uuid(),   # new family for each fresh login
        parent_token_id=None,
        replaced_by_token_id=None,
        token_hash=token_hash,
        device_info=device_info,
        ip_address=ip_address,
        expires_at=expires_at,
        consumed_at=None,
        revoked_at=None,
        created_at=now,
    )
    await refresh_repo.save(refresh)

    # Update last_login_at
    await user_repo.update_last_login(user.user_id, now)

    return LoginResult(
        access_token=access_token,
        refresh_token_raw=raw_token,
        user_id=user.user_id,
        store_id=store_id,
        staff_member_id=staff.staff_member_id,
        permissions=permissions,
    )