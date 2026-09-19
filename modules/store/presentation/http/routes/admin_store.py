"""Admin Merchant Store HTTP routes."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import settings
from app.db.session import SqlAlchemyUnitOfWork, get_uow
from modules.iam.presentation.http.deps import get_current_user_payload, require_permission
from modules.store.infrastructure.db.repository import StoreRepository
from modules.store.presentation.http.schemas.requests import StorePatchRequest
from modules.store.presentation.http.schemas.responses import AdminStoreResponse

router = APIRouter(prefix="/admin/store", tags=["Admin Store Management"])


async def _resolve_store_id(payload: dict, uow: SqlAlchemyUnitOfWork) -> UUID:
    store_id_str = payload.get("store_id")
    if store_id_str:
        return UUID(store_id_str)
    if settings.STORE_ID:
        return UUID(settings.STORE_ID)
    
    store = await StoreRepository(uow.session).get_first_active_store()
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Store not provisioned",
        )
    return store.store_id

@router.get(
    "",
    response_model=AdminStoreResponse,
    dependencies=[Depends(require_permission("store.read"))],
)
async def get_admin_store(
    payload: dict = Depends(get_current_user_payload),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> AdminStoreResponse:
    """Fetch merchant store profile under authenticated staff context."""
    async with uow:
        store_id = await _resolve_store_id(payload, uow)
        store = await StoreRepository(uow.session).get_by_id(store_id)
        if store is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Store not found",
            )
    return AdminStoreResponse.model_validate(store)


@router.patch(
    "",
    response_model=AdminStoreResponse,
    dependencies=[Depends(require_permission("store.write"))],
)
async def update_admin_store(
    body: StorePatchRequest,
    payload: dict = Depends(get_current_user_payload),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> AdminStoreResponse:
    """Update merchant/store profile.
    
    Validates ISO codes/timezone and status changes. Currency modification
    is not permitted without explicit migration rules.
    """
    async with uow:
        store_id = await _resolve_store_id(payload, uow)
        repo = StoreRepository(uow.session)
        store = await repo.get_by_id(store_id)
        if store is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Store not found",
            )
        if body.name is not None:
            store.name = body.name.strip()
        if body.legal_name is not None:
            store.legal_name = body.legal_name.strip() if body.legal_name else None
        if body.country_code is not None:
            store.country_code = body.country_code
        if body.timezone is not None:
            store.timezone = body.timezone.strip()
        if body.status is not None:
            store.status = body.status

        store.version += 1
        store.updated_at = datetime.now(timezone.utc)

        await repo.save(store)
        await uow.commit()

    return AdminStoreResponse.model_validate(store)