from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# UserModel
# ---------------------------------------------------------------------------

class UserModel(Base, TimestampMixin):
    """Login identities for merchant/staff/admin users. Customer accounts are intentionally separate."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_status", "status"),
        Index("ix_users_created_at", "created_at"),
    )

    user_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True), primary_key=True
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="ACTIVE")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    staff_members: Mapped[list[StaffMemberModel]] = relationship(
        "StaffMemberModel", back_populates="user", lazy="raise", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list[RefreshTokenModel]] = relationship(
        "RefreshTokenModel", back_populates="user", lazy="raise", cascade="all, delete-orphan"
    )

class RoleModel(Base):
    """Named staff roles scoped to a store."""

    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("store_id", "name", name="uq_roles_store_name"),
    )

    role_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True), primary_key=True
    )
    store_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("stores.store_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )

    # Relationships
    role_permissions: Mapped[list[RolePermissionModel]] = relationship(
        "RolePermissionModel", back_populates="role", lazy="raise", cascade="all, delete-orphan"
    )
    staff_member_roles: Mapped[list[StaffMemberRoleModel]] = relationship(
        "StaffMemberRoleModel", back_populates="role", lazy="raise", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# PermissionModel
# ---------------------------------------------------------------------------

class PermissionModel(Base):
    """Global permission catalog used by roles."""

    __tablename__ = "permissions"
    __table_args__ = (
        UniqueConstraint("code", name="uq_permissions_code"),
    )

    permission_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True), primary_key=True
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )

    # Relationships
    role_permissions: Mapped[list[RolePermissionModel]] = relationship(
        "RolePermissionModel", back_populates="permission", lazy="raise"
    )


# ---------------------------------------------------------------------------
# RolePermissionModel (M2M)
# ---------------------------------------------------------------------------

class RolePermissionModel(Base):
    """Many-to-many role → permission mapping."""

    __tablename__ = "role_permissions"

    role_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("roles.role_id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("permissions.permission_id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )

    # Relationships
    role: Mapped[RoleModel] = relationship("RoleModel", back_populates="role_permissions", lazy="raise")
    permission: Mapped[PermissionModel] = relationship("PermissionModel", back_populates="role_permissions", lazy="raise")


# ---------------------------------------------------------------------------
# StaffMemberModel
# ---------------------------------------------------------------------------

class StaffMemberModel(Base):
    """Assigns a user identity to a store."""

    __tablename__ = "staff_members"
    __table_args__ = (
        UniqueConstraint("store_id", "user_id", name="uq_staff_members_store_user"),
        Index("ix_staff_members_store_id", "store_id"),
        Index("ix_staff_members_status", "status"),
    )

    staff_member_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True), primary_key=True
    )
    store_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("stores.store_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    display_name: Mapped[str | None] = mapped_column(String(140), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="ACTIVE")
    is_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )

    # Relationships
    user: Mapped[UserModel] = relationship("UserModel", back_populates="staff_members", lazy="raise")
    staff_member_roles: Mapped[list[StaffMemberRoleModel]] = relationship(
        "StaffMemberRoleModel", back_populates="staff_member", lazy="raise", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# StaffMemberRoleModel (M2M)
# ---------------------------------------------------------------------------

class StaffMemberRoleModel(Base):
    """Many-to-many staff → role mapping."""

    __tablename__ = "staff_member_roles"

    staff_member_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("staff_members.staff_member_id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("roles.role_id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )

    # Relationships
    staff_member: Mapped[StaffMemberModel] = relationship("StaffMemberModel", back_populates="staff_member_roles", lazy="raise")
    role: Mapped[RoleModel] = relationship("RoleModel", back_populates="staff_member_roles", lazy="raise")


# ---------------------------------------------------------------------------
# RefreshTokenModel
# ---------------------------------------------------------------------------

class RefreshTokenModel(Base):
    """Server-side refresh-token/session registry with rotation family tracking."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_refresh_tokens_hash"),
        CheckConstraint("parent_token_id IS NULL OR parent_token_id <> token_id", name="chk_parent_token_not_self"),
        CheckConstraint("replaced_by_token_id IS NULL OR replaced_by_token_id <> token_id", name="chk_replaced_token_not_self"),
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_family_id", "family_id"),
        Index("ix_refresh_tokens_expires_at", "expires_at"),
        Index("ix_refresh_tokens_revoked_at", "revoked_at"),
    )

    token_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True), primary_key=True
    )
    user_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    family_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True), nullable=False
    )
    parent_token_id: Mapped[pg.UUID | None] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("refresh_tokens.token_id", ondelete="SET NULL"),
        nullable=True,
    )
    replaced_by_token_id: Mapped[pg.UUID | None] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("refresh_tokens.token_id", ondelete="SET NULL"),
        nullable=True,
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    device_info: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )

    # Relationships
    user: Mapped[UserModel] = relationship("UserModel", back_populates="refresh_tokens", lazy="raise")