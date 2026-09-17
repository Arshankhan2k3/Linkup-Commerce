"""Storefront Public Store HTTP routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import settings
from app.db.session import SqlAlchemyUnitOfWork, get_uow
from modules.store.infrastructure.db.models import StoreModel, StoreSettingsModel
from modules.store.infrastructure.db.repository import (
    StoreRepository,
    StoreSettingsRepository,
)
from modules.store.presentation.http.schemas.responses import StorefrontStoreResponse

router = APIRouter(prefix="/storefront/store", tags=["Storefront Store"])


async def _resolve_store_id(uow: SqlAlchemyUnitOfWork) -> UUID:
    if settings.STORE_ID:
        return UUID(settings.STORE_ID)
    
    # Fallback to single active deployment store in DB
    store = await StoreRepository(uow.session).get_first_active_store()
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Store not provisioned",
        )
    return store.store_id

PUBLIC_SAFE_CONFIG_KEYS = {
    "ga4_id",
    "meta_pixel_id",
    "gtm_id",
    "announcement_bar",
    "social_links",
    "logo_url",
    "favicon_url",
}


@router.get("", response_model=StorefrontStoreResponse)
async def get_storefront_store(
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> StorefrontStoreResponse:
    """
    Return public store identity and safe storefront configuration.
    Exposes only whitelisted public-safe settings. Never exposes secrets,
    gateway keys, internal flags or staff data.
    """
    async with uow:
        store_id = await _resolve_store_id(uow)
        store = await StoreRepository(uow.session).get_by_id(store_id)
        if store is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Store not found",
            )
        settings_model = await StoreSettingsRepository(uow.session).get_by_store(store_id)
    # Filter config JSON blob for public safety wot-4hitelist + public operational settings
    raw_config = settings_model.config if settings_model and settings_model.config else {}
    public_config = {k: v for k, v in raw_config.items() if k.lower() in PUBLIC_SAFE_CONFIG_KEYS}

    if settings_model:
        public_config.update({
            "order_prefix": settings_model.order_prefix,
            "weight_unit": settings_model.weight_unit,
            "dimension_unit": settings_model.dimension_unit,
            "tax_inclusive": settings_model.tax_inclusive,
            "allow_guest_checkout": settings_model.allow_guest_checkout,
            "inventory_policy": settings_model.inventory_policy,
        })

    return StorefrontStoreResponse(
        store_id=store.store_id,
        name=store.name,
        currency=store.currency,
        country=store.country_code,
        timezone=store.timezone,
        public_settings=public_config,
    )
