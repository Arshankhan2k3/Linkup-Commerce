"""Admin Store Settings HTTP routes."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import settings
from app.db.session import SqlAlchemyUnitOfWork, get_uow
from modules.iam.presentation.http.deps import get_current_user_payload, require_permission
from modules.store.infrastructure.db.models import StoreSettingsModel
from modules.store.infrastructure.db.repository import (
    StoreRepository,
    StoreSettingsRepository,
)
from modules.store.presentation.http.schemas.requests import SettingsPatchRequest
from modules.store.presentation.http.schemas.responses import StoreSettingsResponse
from shared.domain.ids import generate_uuid

router = APIRouter(prefix="/admin/settings", tags=["Admin Store Settings"])


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
    response_model=StoreSettingsResponse,
    dependencies=[Depends(require_permission("settings.read"))],
)
async def get_admin_settings(
    payload: dict = Depends(get_current_user_payload),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> StoreSettingsResponse:
    """Fetch merchant operational settings."""
    async with uow:
        store_id = await _resolve_store_id(payload, uow)
        settings_model = await StoreSettingsRepository(uow.session).get_by_store(store_id)
        if settings_model is None:
            # Auto-create baseline settings if missing
            settings_model = StoreSettingsModel(
                setting_id=generate_uuid(),
                store_id=store_id,
            )
            await StoreSettingsRepository(uow.session).save(settings_model)
            await uow.commit()

    return StoreSettingsResponse.model_validate(settings_model)


@router.patch(
    "",
    response_model=StoreSettingsResponse,
    dependencies=[Depends(require_permission("settings.write"))],
)
async def update_admin_settings(
    body: SettingsPatchRequest,
    payload: dict = Depends(get_current_user_payload),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> StoreSettingsResponse:
    """Update operational checkout, tax, unit, and inventory policies.
    
    Release 1 accepts inventory_policy=DENY only.
    """
    async with uow:
        store_id = await _resolve_store_id(payload, uow)
        repo = StoreSettingsRepository(uow.session)
        s = await repo.get_by_store(store_id)
        if s is None:
            s = StoreSettingsModel(
                setting_id=generate_uuid(),
                store_id=store_id,
            )

        if body.order_prefix is not None:
            s.order_prefix = body.order_prefix.strip()
        if body.weight_unit is not None:
            s.weight_unit = body.weight_unit
        if body.dimension_unit is not None:
            s.dimension_unit = body.dimension_unit
        if body.tax_inclusive is not None:
            s.tax_inclusive = body.tax_inclusive
        if body.allow_guest_checkout is not None:
            s.allow_guest_checkout = body.allow_guest_checkout
        if body.inventory_policy is not None:
            if body.inventory_policy != "DENY":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Release 1 accepts inventory_policy=DENY only",
                )
            s.inventory_policy = body.inventory_policy
        if body.checkout_expiry_minutes is not None:
            s.checkout_expiry_minutes = body.checkout_expiry_minutes

        s.version += 1
        s.updated_at = datetime.now(timezone.utc)

        await repo.save(s)
        await uow.commit()

    return StoreSettingsResponse.model_validate(s)
