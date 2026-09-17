"""Refresh token command — rotate refresh token with family protection.

Algorithm
---------
1. Hash the incoming raw token.
2. Look up by hash in DB.
3. If NOT FOUND → raise 401.
4. If REVOKED or CONSUMED → token reuse attack → revoke entire family → raise 401.
5. If EXPIRED → raise 401.
6. Mark old token consumed & set replaced_by_token_id.
7. Issue new refresh token in the SAME family_id with parent_token_id set.
8. Issue new access token.
9. Return LoginResult.

Caller must call uow.commit() — this handler does NOT commit.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from modules.iam.application.commands.login_user import LoginResult
from modules.iam.application.services.token_service import create_access_token
from modules.iam.infrastructure.db.models import RefreshTokenModel, StaffMemberModel
from modules.iam.infrastructure.db.repository import (
    RefreshTokenRepository,
    StaffMemberRepository,
    UserRepository,
)
from shared.domain.exceptions import UnauthorizedActionError
from shared.domain.ids import generate_uuid


async def refresh_token(
    *,
    user_repo: UserRepository,
    staff_repo: StaffMemberRepository,
    refresh_repo: RefreshTokenRepository,
    raw_token: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> LoginResult:
    """Rotate a refresh token. Raises UnauthorizedActionError on any violation."""
    token_hash = refresh_repo.hash_token(raw_token)
    record = await refresh_repo.get_by_hash(token_hash)

    if record is None:
        raise UnauthorizedActionError("Refresh token not found")

    if record.revoked_at is not None or record.consumed_at is not None:
        # Token reuse or revoked — security breach response → revoke entire family
        await refresh_repo.revoke_family(record.family_id)
        raise UnauthorizedActionError("Refresh token invalid or already consumed — family revoked")

    now = datetime.now(timezone.utc)
    if record.expires_at < now:
        raise UnauthorizedActionError("Refresh token expired")

    # Fetch user
    user = await user_repo.get_by_id(record.user_id)
    if user is None or user.status != "ACTIVE":
        raise UnauthorizedActionError("User not found or inactive")

    # Issue new refresh token in SAME family
    new_token_id = generate_uuid()
    new_raw = refresh_repo.generate_raw()
    new_hash = refresh_repo.hash_token(new_raw)
    expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    device_info: dict[str, Any] = record.device_info or {}
    if user_agent:
        device_info["user_agent"] = user_agent

    new_record = RefreshTokenModel(
        token_id=new_token_id,
        user_id=user.user_id,
        family_id=record.family_id,   # SAME family
        parent_token_id=record.token_id,
        replaced_by_token_id=None,
        token_hash=new_hash,
        device_info=device_info,
        ip_address=ip_address or record.ip_address,
        expires_at=expires_at,
        consumed_at=None,
        revoked_at=None,
        created_at=now,
    )
    await refresh_repo.save(new_record)

    # Consume old token and point to replacement
    await refresh_repo.mark_consumed_and_replace(record.token_id, new_token_id)

    # Fetch active staff membership and permissions
    result = await staff_repo._session.execute(
        select(StaffMemberModel).where(
            StaffMemberModel.user_id == user.user_id,
            StaffMemberModel.status == "ACTIVE",
        )
    )
    staff = result.scalars().first()

    store_id: UUID
    staff_member_id: UUID | None = None
    permissions: list[str] = []

    if staff:
        store_id = staff.store_id
        staff_member_id = staff.staff_member_id
        permissions = await staff_repo.get_permission_codes(staff.staff_member_id)
    else:
        if settings.STORE_ID:
            store_id = UUID(settings.STORE_ID)
        else:
            store_id = user.user_id

    # Issue new access token
    access_token = create_access_token(
        user_id=user.user_id,
        store_id=store_id,
        staff_member_id=staff_member_id,
        permissions=permissions,
    )

    return LoginResult(
        access_token=access_token,
        refresh_token_raw=new_raw,
        user_id=user.user_id,
        store_id=store_id,
        staff_member_id=staff_member_id,
        permissions=permissions,
    )
