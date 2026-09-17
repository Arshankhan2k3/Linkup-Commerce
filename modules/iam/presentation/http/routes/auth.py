"""IAM auth routes — login, refresh, logout, logout-all, me, accept-invite."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SqlAlchemyUnitOfWork, get_uow
from modules.iam.application.commands.login_user import login_user
from modules.iam.application.commands.refresh_token import refresh_token as rotate_refresh
from modules.iam.infrastructure.db.models import StaffMemberModel, UserModel
from modules.iam.infrastructure.db.repository import (
    RefreshTokenRepository,
    RoleRepository,
    StaffMemberRepository,
    UserRepository,
)
from modules.iam.presentation.http.deps import (
    get_current_user_id,
    get_current_user_payload,
)
from modules.iam.presentation.http.schemas.requests import (
    AcceptInviteRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
)
from modules.iam.presentation.http.schemas.responses import (
    MeResponse,
    RoleResponse,
    StaffMemberResponse,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["IAM Authentication"])


def _get_store_id() -> UUID:
    sid = settings.STORE_ID
    if not sid:
        raise HTTPException(status_code=503, detail="Store not provisioned")
    return UUID(sid)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> TokenResponse:
    store_id = _get_store_id()
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else None

    async with uow:
        user_repo = UserRepository(uow.session)
        staff_repo = StaffMemberRepository(uow.session)
        refresh_repo = RefreshTokenRepository(uow.session)

        result = await login_user(
            user_repo=user_repo,
            staff_repo=staff_repo,
            refresh_repo=refresh_repo,
            store_id=store_id,
            email=str(body.email),
            password=body.password,
            user_agent=user_agent,
            ip_address=client_ip,
        )
        staff_model = None
        if result.staff_member_id:
            staff_model = await staff_repo.get_by_id(result.staff_member_id)
        await uow.commit()

    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token_raw,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        staff=StaffMemberResponse.model_validate(staff_model) if staff_model else None,
        permissions=result.permissions,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    request: Request,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> TokenResponse:
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else None

    async with uow:
        result = await rotate_refresh(
            user_repo=UserRepository(uow.session),
            staff_repo=StaffMemberRepository(uow.session),
            refresh_repo=RefreshTokenRepository(uow.session),
            raw_token=body.refresh_token,
            user_agent=user_agent,
            ip_address=client_ip,
        )
        await uow.commit()

    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token_raw,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        permissions=result.permissions,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutRequest,
    payload: dict = Depends(get_current_user_payload),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> None:
    async with uow:
        repo = RefreshTokenRepository(uow.session)
        if body.refresh_token:
            token_hash = repo.hash_token(body.refresh_token)
            record = await repo.get_by_hash(token_hash)
            if record:
                await repo.revoke_family(record.family_id)
        else:
            user_id = UUID(payload["sub"])
            await repo.revoke_all_for_user(user_id)
        await uow.commit()


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    payload: dict = Depends(get_current_user_payload),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> None:
    user_id = UUID(payload["sub"])
    async with uow:
        repo = RefreshTokenRepository(uow.session)
        await repo.revoke_all_for_user(user_id)
        await uow.commit()


@router.get("/me", response_model=MeResponse)
async def me(
    payload: dict = Depends(get_current_user_payload),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> MeResponse:
    user_id = UUID(payload["sub"])
    store_id = _get_store_id()

    async with uow:
        user = await UserRepository(uow.session).get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User identity not found")

        staff_repo = StaffMemberRepository(uow.session)
        staff = await staff_repo.get_by_user_and_store(user_id, store_id)

        roles_list: list[RoleResponse] = []
        permissions_list: list[str] = []
        if staff:
            permissions_list = await staff_repo.get_permission_codes(staff.staff_member_id)
            roles = await staff_repo.get_roles(staff.staff_member_id)
            role_repo = RoleRepository(uow.session)
            for r in roles:
                p_codes = await role_repo.get_permission_codes_for_role(r.role_id)
                roles_list.append(
                    RoleResponse(
                        role_id=r.role_id,
                        store_id=r.store_id,
                        name=r.name,
                        is_system=r.is_system,
                        description=r.description,
                        created_at=r.created_at,
                        permission_codes=p_codes,
                    )
                )

    return MeResponse(
        user=UserResponse.model_validate(user),
        staff_member=StaffMemberResponse.model_validate(staff) if staff else None,
        roles=roles_list,
        permissions=permissions_list,
    )


@router.post("/accept-invite", response_model=TokenResponse)
async def accept_invite(
    body: AcceptInviteRequest,
    request: Request,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> TokenResponse:
    store_id = _get_store_id()
    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else None

    # Verify signed token format or lookup pending user by token/id
    async with uow:
        user_repo = UserRepository(uow.session)
        staff_repo = StaffMemberRepository(uow.session)
        refresh_repo = RefreshTokenRepository(uow.session)

        # Look up invited staff by token string (or ID)
        try:
            invited_user_id = UUID(body.invite_token)
            user = await user_repo.get_by_id(invited_user_id)
        except ValueError:
            user = await user_repo.get_by_email(body.invite_token)

        if user is None:
            raise HTTPException(status_code=400, detail="Invalid or expired invitation token")

        # Set user password and activate status
        user.password_hash = hash_password(body.password)
        user.status = "ACTIVE"
        await user_repo.save(user)

        staff = await staff_repo.get_by_user_and_store(user.user_id, store_id)
        if staff:
            staff.status = "ACTIVE"
            if body.name:
                staff.display_name = body.name
            await staff_repo.save(staff)

        result = await login_user(
            user_repo=user_repo,
            staff_repo=staff_repo,
            refresh_repo=refresh_repo,
            store_id=store_id,
            email=user.email,
            password=body.password,
            user_agent=user_agent,
            ip_address=client_ip,
        )
        await uow.commit()

    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token_raw,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        permissions=result.permissions,
    )