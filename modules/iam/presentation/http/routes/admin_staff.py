"""IAM admin staff routes — invitations, list, update, delete, roles assignment."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SqlAlchemyUnitOfWork, get_uow
from modules.iam.infrastructure.db.models import StaffMemberModel, UserModel
from modules.iam.infrastructure.db.repository import (
    RefreshTokenRepository,
    RoleRepository,
    StaffMemberRepository,
    UserRepository,
)
from modules.iam.presentation.http.deps import (
    get_current_store_id,
    get_current_user_payload,
    require_permission,
)
from modules.iam.presentation.http.schemas.requests import (
    StaffInviteRequest,
    StaffRolesUpdateRequest,
    StaffUpdateRequest,
)
from modules.iam.presentation.http.schemas.responses import (
    InvitationResponse,
    StaffMemberResponse,
)
from shared.domain.ids import generate_uuid

router = APIRouter(prefix="/admin/staff", tags=["IAM Staff Management"])


def _get_store_id() -> UUID:
    sid = settings.STORE_ID
    if not sid:
        raise HTTPException(status_code=503, detail="Store not provisioned")
    return UUID(sid)


@router.post("/invitations", response_model=InvitationResponse, dependencies=[Depends(require_permission("staff.manage"))])
async def invite_staff(
    body: StaffInviteRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> InvitationResponse:
    store_id = _get_store_id()

    async with uow:
        user_repo = UserRepository(uow.session)
        staff_repo = StaffMemberRepository(uow.session)

        # Check existing user
        user = await user_repo.get_by_email(body.email)
        if user is None:
            user = UserModel(
                user_id=generate_uuid(),
                email=str(body.email),
                password_hash=hash_password(generate_uuid().hex),  # random unverified password
                status="INVITED",
            )
            await user_repo.save(user)

        # Check existing staff member
        staff = await staff_repo.get_by_user_and_store(user.user_id, store_id)
        if staff is None:
            staff = StaffMemberModel(
                staff_member_id=generate_uuid(),
                store_id=store_id,
                user_id=user.user_id,
                display_name=str(body.email).split("@")[0],
                status="INVITED",
                is_owner=False,
            )
            await staff_repo.save(staff)

        if body.role_ids:
            await staff_repo.set_roles(staff.staff_member_id, body.role_ids)

        await uow.commit()

    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    return InvitationResponse(
        invitation_id=staff.staff_member_id,
        status="INVITED",
        expires_at=expires_at,
        invite_token=str(user.user_id),
    )


@router.get("", response_model=list[StaffMemberResponse], dependencies=[Depends(require_permission("staff.read"))])
async def list_staff(
    status_filter: str | None = None,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> list[StaffMemberResponse]:
    store_id = _get_store_id()
    async with uow:
        members = await StaffMemberRepository(uow.session).list_by_store(store_id, status=status_filter)
    return [StaffMemberResponse.model_validate(m) for m in members]


@router.patch("/{staff_id}", response_model=StaffMemberResponse, dependencies=[Depends(require_permission("staff.manage"))])
async def update_staff(
    staff_id: UUID,
    body: StaffUpdateRequest,
    payload: dict = Depends(get_current_user_payload),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> StaffMemberResponse:
    store_id = _get_store_id()
    async with uow:
        staff_repo = StaffMemberRepository(uow.session)
        member = await staff_repo.get_by_id(staff_id)
        if member is None or member.store_id != store_id:
            raise HTTPException(status_code=404, detail="Staff member not found")

        # Prevent owner lockout
        if member.is_owner and body.status and body.status != "ACTIVE":
            owners_count = await staff_repo.count_owners(store_id)
            if owners_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot deactivate the last active store owner")

        if body.display_name is not None:
            member.display_name = body.display_name
        if body.status is not None:
            member.status = body.status

        await staff_repo.save(member)
        await uow.commit()

    return StaffMemberResponse.model_validate(member)


@router.delete("/{staff_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("staff.manage"))])
async def delete_staff(
    staff_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> None:
    store_id = _get_store_id()
    async with uow:
        staff_repo = StaffMemberRepository(uow.session)
        member = await staff_repo.get_by_id(staff_id)
        if member is None or member.store_id != store_id:
            raise HTTPException(status_code=404, detail="Staff member not found")

        if member.is_owner:
            owners_count = await staff_repo.count_owners(store_id)
            if owners_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot remove the last active store owner")

        # Soft-disable membership and revoke sessions
        member.status = "DISABLED"
        await staff_repo.save(member)

        refresh_repo = RefreshTokenRepository(uow.session)
        await refresh_repo.revoke_all_for_user(member.user_id)

        await uow.commit()


@router.put("/{staff_id}/roles", response_model=StaffMemberResponse, dependencies=[Depends(require_permission("staff.manage"))])
async def update_staff_roles(
    staff_id: UUID,
    body: StaffRolesUpdateRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> StaffMemberResponse:
    store_id = _get_store_id()
    async with uow:
        staff_repo = StaffMemberRepository(uow.session)
        member = await staff_repo.get_by_id(staff_id)
        if member is None or member.store_id != store_id:
            raise HTTPException(status_code=404, detail="Staff member not found")

        await staff_repo.set_roles(staff_id, body.role_ids)
        await uow.commit()

    return StaffMemberResponse.model_validate(member)
