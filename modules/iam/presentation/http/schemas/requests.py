"""IAM HTTP schemas — request models."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = None

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class StaffInviteRequest(BaseModel):
    email: EmailStr
    role_ids: list[UUID] = []


class AcceptInviteRequest(BaseModel):
    invite_token: str
    password: str
    name: str | None = None

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class StaffUpdateRequest(BaseModel):
    status: str | None = None
    display_name: str | None = None


class StaffRolesUpdateRequest(BaseModel):
    role_ids: list[UUID]


class CreateRoleRequest(BaseModel):
    name: str
    description: str | None = None
    permission_codes: list[str] = []


class UpdateRoleRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    permission_codes: list[str] | None = None