"""Store HTTP routes — 6 endpoints.

Routes use async with uow: pattern. No db.commit() ever.
store_id comes from settings.STORE_ID (single-tenant).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import settings
from app.db.session import SqlAlchemyUnitOfWork, get_uow
from modules.store.application.commands.create_store import create_store
from modules.store.infrastructure.db.models import SalesChannelModel
from modules.store.infrastructure.db.repository import (
    SalesChannelRepository,
    StoreRepository,
    StoreSettingsRepository,
)
from modules.store.presentation.http.schemas.requests import (
    CreateSalesChannelRequest,
    CreateStoreRequest,
    UpdateStoreRequest,
    UpdateStoreSettingsRequest,
)
from modules.store.presentation.http.schemas.responses import (
    SalesChannelResponse,
    StoreResponse,
    StoreSettingsResponse,
)
from shared.domain.ids import generate_uuid

router = APIRouter(prefix="/store", tags=["Store"])


def _get_store_id() -> UUID:
    sid = settings.STORE_ID
    if not sid:
        raise HTTPException(status_code=503, detail="Store not provisioned")
    return UUID(sid)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=StoreResponse)
async def create_store_endpoint(
    body: CreateStoreRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> StoreResponse:
    async with uow:
        store_id = await create_store(
            store_repo=StoreRepository(uow.session),
            settings_repo=StoreSettingsRepository(uow.session),
            name=body.name,
            slug=body.slug,
            email=str(body.email),
            country_code=body.country_code,
            currency=body.currency,
            timezone_str=body.timezone,
            legal_name=body.legal_name,
            phone=body.phone,
        )
        await uow.commit()
        # Set active STORE_ID for runtime context
        settings.STORE_ID = str(store_id)
        store = await StoreRepository(uow.session).get_by_id(store_id)
    return StoreResponse.model_validate(store)


@router.get("", response_model=StoreResponse)
async def get_store(
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> StoreResponse:
    store_id = _get_store_id()
    async with uow:
        store = await StoreRepository(uow.session).get_by_id(store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    return StoreResponse.model_validate(store)


@router.patch("", response_model=StoreResponse)
async def update_store(
    body: UpdateStoreRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> StoreResponse:
    store_id = _get_store_id()
    async with uow:
        repo = StoreRepository(uow.session)
        store = await repo.get_by_id(store_id)
        if store is None:
            raise HTTPException(status_code=404, detail="Store not found")

        if body.name is not None:
            store.name = body.name
        if body.legal_name is not None:
            store.legal_name = body.legal_name
        if body.phone is not None:
            store.phone = body.phone
        if body.timezone is not None:
            store.timezone = body.timezone
        store.updated_at = datetime.now(timezone.utc)

        await repo.save(store)
        await uow.commit()
    return StoreResponse.model_validate(store)


@router.get("/settings", response_model=StoreSettingsResponse)
async def get_settings(
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> StoreSettingsResponse:
    store_id = _get_store_id()
    async with uow:
        settings_model = await StoreSettingsRepository(uow.session).get_by_store(store_id)
    if settings_model is None:
        raise HTTPException(status_code=404, detail="Store settings not found")
    return StoreSettingsResponse.model_validate(settings_model)


@router.put("/settings", response_model=StoreSettingsResponse)
async def update_settings(
    body: UpdateStoreSettingsRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> StoreSettingsResponse:
    store_id = _get_store_id()
    async with uow:
        repo = StoreSettingsRepository(uow.session)
        s = await repo.get_by_store(store_id)
        if s is None:
            raise HTTPException(status_code=404, detail="Store settings not found")

        for field, value in body.model_dump(exclude_none=True).items():
            setattr(s, field, value)

        await repo.save(s)
        await uow.commit()
    return StoreSettingsResponse.model_validate(s)


@router.get("/sales-channels", response_model=list[SalesChannelResponse])
async def list_channels(
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> list[SalesChannelResponse]:
    store_id = _get_store_id()
    async with uow:
        channels = await SalesChannelRepository(uow.session).list_by_store(store_id)
    return [SalesChannelResponse.model_validate(c) for c in channels]


@router.post("/sales-channels", status_code=status.HTTP_201_CREATED, response_model=SalesChannelResponse)
async def create_channel(
    body: CreateSalesChannelRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> SalesChannelResponse:
    store_id = _get_store_id()
    async with uow:
        channel = SalesChannelModel(
            channel_id=generate_uuid(),
            store_id=store_id,
            name=body.name,
            channel_type=body.channel_type,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        await SalesChannelRepository(uow.session).save(channel)
        await uow.commit()
    return SalesChannelResponse.model_validate(channel)


@router.delete("/sales-channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(
    channel_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> None:
    async with uow:
        repo = SalesChannelRepository(uow.session)
        channel = await repo.get_by_id(channel_id)
        if channel is None:
            raise HTTPException(status_code=404, detail="Channel not found")
        await repo.delete(channel)
        await uow.commit()