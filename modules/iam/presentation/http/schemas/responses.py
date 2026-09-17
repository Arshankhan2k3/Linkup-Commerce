"""IAM HTTP schemas — response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    staff: StaffMemberResponse | None = None
    permissions: list[str] = []


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    email: str
    phone: str | None = None
    status: str
    email_verified_at: datetime | None = None
    last_login_at: datetime | None = None
    created_at: datetime


class StaffMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    staff_member_id: UUID
    store_id: UUID
    user_id: UUID
    display_name: str | None = None
    status: str
    is_owner: bool
    created_at: datetime


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role_id: UUID
    store_id: UUID
    name: str
    is_system: bool
    description: str | None = None
    created_at: datetime
    permission_codes: list[str] = []


class MeResponse(BaseModel):
    user: UserResponse
    staff_member: StaffMemberResponse | None = None
    roles: list[RoleResponse] = []
    permissions: list[str] = []


class InvitationResponse(BaseModel):
    invitation_id: UUID
    status: str
    expires_at: datetime
    invite_token: str | None = None