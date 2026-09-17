"""IAM repository — SQLAlchemy implementations.

All repositories accept an AsyncSession (from UnitOfWork.session).
None of them call commit() or rollback() — that is the UoW's job.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    PermissionModel,
    RefreshTokenModel,
    RoleModel,
    RolePermissionModel,
    StaffMemberModel,
    StaffMemberRoleModel,
    UserModel,
)


# ---------------------------------------------------------------------------
# UserRepository
# ---------------------------------------------------------------------------

class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> UserModel | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> UserModel | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        return result.scalar_one_or_none()

    async def save(self, user: UserModel) -> None:
        self._session.add(user)
        await self._session.flush()

    async def update_last_login(self, user_id: UUID, at: datetime) -> None:
        await self._session.execute(
            update(UserModel)
            .where(UserModel.user_id == user_id)
            .values(last_login_at=at)
        )


# ---------------------------------------------------------------------------
# PermissionRepository
# ---------------------------------------------------------------------------

class PermissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[PermissionModel]:
        result = await self._session.execute(select(PermissionModel))
        return list(result.scalars().all())

    async def get_by_codes(self, codes: list[str]) -> list[PermissionModel]:
        if not codes:
            return []
        result = await self._session.execute(
            select(PermissionModel).where(PermissionModel.code.in_(codes))
        )
        return list(result.scalars().all())

    async def save(self, permission: PermissionModel) -> None:
        self._session.add(permission)
        await self._session.flush()


# ---------------------------------------------------------------------------
# RoleRepository
# ---------------------------------------------------------------------------

class RoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, role_id: UUID) -> RoleModel | None:
        result = await self._session.execute(
            select(RoleModel).where(RoleModel.role_id == role_id)
        )
        return result.scalar_one_or_none()

    async def list_by_store(self, store_id: UUID) -> list[RoleModel]:
        result = await self._session.execute(
            select(RoleModel).where(RoleModel.store_id == store_id)
        )
        return list(result.scalars().all())

    async def get_by_store_and_name(self, store_id: UUID, name: str) -> RoleModel | None:
        result = await self._session.execute(
            select(RoleModel).where(
                RoleModel.store_id == store_id,
                RoleModel.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def save(self, role: RoleModel) -> None:
        self._session.add(role)
        await self._session.flush()

    async def delete(self, role: RoleModel) -> None:
        await self._session.delete(role)
        await self._session.flush()

    async def get_permission_codes_for_role(self, role_id: UUID) -> list[str]:
        result = await self._session.execute(
            select(PermissionModel.code)
            .join(RolePermissionModel, RolePermissionModel.permission_id == PermissionModel.permission_id)
            .where(RolePermissionModel.role_id == role_id)
        )
        return list(result.scalars().all())

    async def set_permissions_by_codes(self, role_id: UUID, permission_codes: list[str]) -> None:
        # Clear existing
        await self._session.execute(
            delete(RolePermissionModel).where(RolePermissionModel.role_id == role_id)
        )
        if not permission_codes:
            return
        perms = await PermissionRepository(self._session).get_by_codes(permission_codes)
        for perm in perms:
            self._session.add(RolePermissionModel(role_id=role_id, permission_id=perm.permission_id))
        await self._session.flush()


# ---------------------------------------------------------------------------
# StaffMemberRepository
# ---------------------------------------------------------------------------

class StaffMemberRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, staff_member_id: UUID) -> StaffMemberModel | None:
        result = await self._session.execute(
            select(StaffMemberModel).where(StaffMemberModel.staff_member_id == staff_member_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_and_store(self, user_id: UUID, store_id: UUID) -> StaffMemberModel | None:
        result = await self._session.execute(
            select(StaffMemberModel).where(
                StaffMemberModel.user_id == user_id,
                StaffMemberModel.store_id == store_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_store(self, store_id: UUID, status: str | None = None) -> list[StaffMemberModel]:
        stmt = select(StaffMemberModel).where(StaffMemberModel.store_id == store_id)
        if status:
            stmt = stmt.where(StaffMemberModel.status == status)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_owners(self, store_id: UUID) -> int:
        result = await self._session.execute(
            select(StaffMemberModel).where(
                StaffMemberModel.store_id == store_id,
                StaffMemberModel.is_owner.is_(True),
                StaffMemberModel.status == "ACTIVE",
            )
        )
        return len(result.scalars().all())

    async def save(self, member: StaffMemberModel) -> None:
        self._session.add(member)
        await self._session.flush()

    async def get_permission_codes(self, staff_member_id: UUID) -> list[str]:
        """Return all distinct permission codes for a staff member via their assigned roles."""
        result = await self._session.execute(
            select(PermissionModel.code)
            .join(RolePermissionModel, RolePermissionModel.permission_id == PermissionModel.permission_id)
            .join(StaffMemberRoleModel, StaffMemberRoleModel.role_id == RolePermissionModel.role_id)
            .where(StaffMemberRoleModel.staff_member_id == staff_member_id)
            .distinct()
        )
        return list(result.scalars().all())

    async def get_roles(self, staff_member_id: UUID) -> list[RoleModel]:
        result = await self._session.execute(
            select(RoleModel)
            .join(StaffMemberRoleModel, StaffMemberRoleModel.role_id == RoleModel.role_id)
            .where(StaffMemberRoleModel.staff_member_id == staff_member_id)
        )
        return list(result.scalars().all())

    async def set_roles(self, staff_member_id: UUID, role_ids: list[UUID]) -> None:
        await self._session.execute(
            delete(StaffMemberRoleModel).where(StaffMemberRoleModel.staff_member_id == staff_member_id)
        )
        for r_id in role_ids:
            self._session.add(StaffMemberRoleModel(staff_member_id=staff_member_id, role_id=r_id))
        await self._session.flush()


# ---------------------------------------------------------------------------
# RefreshTokenRepository
# ---------------------------------------------------------------------------

class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def hash_token(raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def generate_raw() -> str:
        return secrets.token_urlsafe(48)

    async def save(self, token: RefreshTokenModel) -> None:
        self._session.add(token)
        await self._session.flush()

    async def get_by_hash(self, token_hash: str) -> RefreshTokenModel | None:
        result = await self._session.execute(
            select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def mark_consumed_and_replace(self, token_id: UUID, replaced_by_id: UUID) -> None:
        now = datetime.now(timezone.utc)
        await self._session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.token_id == token_id)
            .values(consumed_at=now, replaced_by_token_id=replaced_by_id)
        )

    async def revoke_family(self, family_id: UUID) -> None:
        """Revoke all tokens in a rotation family (security breach response)."""
        now = datetime.now(timezone.utc)
        await self._session.execute(
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.family_id == family_id,
                RefreshTokenModel.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        """Revoke all tokens for a user identity."""
        now = datetime.now(timezone.utc)
        await self._session.execute(
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )