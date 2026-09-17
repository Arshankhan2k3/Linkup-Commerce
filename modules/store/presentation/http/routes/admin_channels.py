"""Admin Sales Channels HTTP routes."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import settings
from app.db.session import SqlAlchemyUnitOfWork, get_uow
from modules.iam.presentation.http.deps import get_current_user_payload, require_permission
from modules.store.infrastructure.db.models import SalesChannelModel
from modules.store.infrastructure.db.repository import (
    SalesChannelRepository,
    StoreRepository,
)
from modules.store.presentation.http.schemas.requests import (
    SalesChannelCreateRequest,
    SalesChannelPatchRequest,
)
from modules.store.presentation.http.schemas.responses import (
    PageInfo,
    SalesChannelConnection,
    SalesChannelResponse,
)
from shared.domain.ids import generate_uuid

router = APIRouter(prefix="/admin/sales-channels", tags=["Admin Sales Channels"])


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
    response_model=SalesChannelConnection,
    dependencies=[Depends(require_permission("channels.read"))],
)
async def list_sales_channels(
    first: int = Query(default=25, ge=1, le=100),
    after: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    payload: dict = Depends(get_current_user_payload),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> SalesChannelConnection:
    """Store-scoped cursor-paginated sales channels listing."""
    async with uow:
        store_id = await _resolve_store_id(payload, uow)
        channels = await SalesChannelRepository(uow.session).list_by_store(
            store_id=store_id,
            first=first,
            after=after,
            status=status_filter,
        )

    has_next_page = len(channels) > first
    items = channels[:first]
    end_cursor = str(items[-1].channel_id) if items and has_next_page else None

    return SalesChannelConnection(
        items=[SalesChannelResponse.model_validate(c) for c in items],
        page_info=PageInfo(
            has_next_page=has_next_page,
            end_cursor=end_cursor,
        ),
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SalesChannelResponse,
    dependencies=[Depends(require_permission("channels.write"))],
)
async def create_sales_channel(
    body: SalesChannelCreateRequest,
    payload: dict = Depends(get_current_user_payload),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> SalesChannelResponse:
    """Create a custom/manual/API sales channel.
    
    Validates known channel type and safe config schema.
    """
    async with uow:
        store_id = await _resolve_store_id(payload, uow)
        repo = SalesChannelRepository(uow.session)
        
        # Check duplicate channel name per store
        existing = await repo.get_by_name(store_id, body.name.strip())
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Sales channel with name '{body.name}' already exists for this store",
            )

        channel = SalesChannelModel(
            channel_id=generate_uuid(),
            store_id=store_id,
            name=body.name.strip(),
            channel_type=body.channel_type,
            status="ACTIVE",
            config=body.config or {},
            version=1,
            created_at=datetime.now(timezone.utc),
        )
        await repo.save(channel)
        await uow.commit()

    return SalesChannelResponse.model_validate(channel)


@router.patch(
    "/{channel_id}",
    response_model=SalesChannelResponse,
    dependencies=[Depends(require_permission("channels.write"))],
)
async def patch_sales_channel(
    channel_id: UUID,
    body: SalesChannelPatchRequest,
    payload: dict = Depends(get_current_user_payload),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> SalesChannelResponse:
    """Update sales channel name, status, or config."""
    async with uow:
        store_id = await _resolve_store_id(payload, uow)
        repo = SalesChannelRepository(uow.session)
        channel = await repo.get_by_id(channel_id)
        if channel is None or channel.store_id != store_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sales channel not found",
            )

        if body.name is not None:
            new_name = body.name.strip()
            if new_name != channel.name:
                dup = await repo.get_by_name(store_id, new_name)
                if dup and dup.channel_id != channel_id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Sales channel with name '{new_name}' already exists",
                    )
                channel.name = new_name

        if body.status is not None:
            channel.status = body.status

        if body.config is not None:
            channel.config = body.config

        channel.version += 1
        await repo.save(channel)
        await uow.commit()

    return SalesChannelResponse.model_validate(channel)
