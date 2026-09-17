"""IAM admin roles routes — list, create, update, delete roles."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import settings
from app.db.session import SqlAlchemyUnitOfWork, get_uow
from modules.iam.infrastructure.db.models import RoleModel
from modules.iam.infrastructure.db.repository import RoleRepository
from modules.iam.presentation.http.deps import require_permission
from modules.iam.presentation.http.schemas.requests import (
    CreateRoleRequest,
    UpdateRoleRequest,
)
from modules.iam.presentation.http.schemas.responses import RoleResponse
from shared.domain.ids import generate_uuid

router = APIRouter(prefix="/admin/roles", tags=["IAM Role Management"])


def _get_store_id() -> UUID:
    sid = settings.STORE_ID
    if not sid:
        raise HTTPException(status_code=503, detail="Store not provisioned")
    return UUID(sid)


@router.get("", response_model=list[RoleResponse], dependencies=[Depends(require_permission("roles.read"))])
async def list_roles(
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> list[RoleResponse]:
    store_id = _get_store_id()
    async with uow:
        repo = RoleRepository(uow.session)
        roles = await repo.list_by_store(store_id)
        result: list[RoleResponse] = []
        for r in roles:
            p_codes = await repo.get_permission_codes_for_role(r.role_id)
            result.append(
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
    return result


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("roles.manage"))])
async def create_role(
    body: CreateRoleRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> RoleResponse:
    store_id = _get_store_id()
    async with uow:
        repo = RoleRepository(uow.session)
        existing = await repo.get_by_store_and_name(store_id, body.name)
        if existing:
            raise HTTPException(status_code=400, detail=f"Role with name '{body.name}' already exists in store")

        role = RoleModel(
            role_id=generate_uuid(),
            store_id=store_id,
            name=body.name,
            description=body.description,
            is_system=False,
        )
        await repo.save(role)
        if body.permission_codes:
            await repo.set_permissions_by_codes(role.role_id, body.permission_codes)

        await uow.commit()

        p_codes = await repo.get_permission_codes_for_role(role.role_id)

    return RoleResponse(
        role_id=role.role_id,
        store_id=role.store_id,
        name=role.name,
        is_system=role.is_system,
        description=role.description,
        created_at=role.created_at,
        permission_codes=p_codes,
    )


@router.patch("/{role_id}", response_model=RoleResponse, dependencies=[Depends(require_permission("roles.manage"))])
async def update_role(
    role_id: UUID,
    body: UpdateRoleRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> RoleResponse:
    store_id = _get_store_id()
    async with uow:
        repo = RoleRepository(uow.session)
        role = await repo.get_by_id(role_id)
        if role is None or role.store_id != store_id:
            raise HTTPException(status_code=404, detail="Role not found")

        if role.is_system:
            raise HTTPException(status_code=400, detail="Cannot edit protected built-in system role")

        if body.name is not None:
            role.name = body.name
        if body.description is not None:
            role.description = body.description

        await repo.save(role)

        if body.permission_codes is not None:
            await repo.set_permissions_by_codes(role.role_id, body.permission_codes)

        await uow.commit()
        p_codes = await repo.get_permission_codes_for_role(role.role_id)

    return RoleResponse(
        role_id=role.role_id,
        store_id=role.store_id,
        name=role.name,
        is_system=role.is_system,
        description=role.description,
        created_at=role.created_at,
        permission_codes=p_codes,
    )


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("roles.manage"))])
async def delete_role(
    role_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> None:
    store_id = _get_store_id()
    async with uow:
        repo = RoleRepository(uow.session)
        role = await repo.get_by_id(role_id)
        if role is None or role.store_id != store_id:
            raise HTTPException(status_code=404, detail="Role not found")

        if role.is_system:
            raise HTTPException(status_code=400, detail="Cannot delete protected built-in system role")

        await repo.delete(role)
        await uow.commit()
