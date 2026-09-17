"""Store repository — SQLAlchemy implementations.

No commit() calls here — that is the UoW's responsibility.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import SalesChannelModel, StoreModel, StoreSettingsModel


class StoreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, store_id: UUID) -> StoreModel | None:
        result = await self._session.execute(
            select(StoreModel).where(StoreModel.store_id == store_id)
        )
        return result.scalar_one_or_none()
    async def get_first_active_store(self) -> StoreModel | None:
        result = await self._session.execute(
            select(StoreModel).order_by(StoreModel.created_at.asc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> StoreModel | None:
        result = await self._session.execute(
            select(StoreModel).where(StoreModel.slug == slug)
        )
        return result.scalar_one_or_none()
    async def save(self, store: StoreModel) -> None:
        self._session.add(store)
        await self._session.flush()


class StoreSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_store(self, store_id: UUID) -> StoreSettingsModel | None:
        result = await self._session.execute(
            select(StoreSettingsModel).where(StoreSettingsModel.store_id == store_id)
        )
        return result.scalar_one_or_none()

    async def save(self, settings_model: StoreSettingsModel) -> None:
        self._session.add(settings_model)
        await self._session.flush()


class SalesChannelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_store(
        self,
        store_id: UUID,
        first: int = 25,
        after: str | None = None,
        status: str | None = None,
    ) -> list[SalesChannelModel]:
        stmt = select(SalesChannelModel).where(SalesChannelModel.store_id == store_id)
        if status:
            stmt = stmt.where(SalesChannelModel.status == status.upper())
        
        stmt = stmt.order_by(SalesChannelModel.created_at.asc(), SalesChannelModel.channel_id.asc())
        stmt = stmt.limit(first + 1)
        
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, channel_id: UUID) -> SalesChannelModel | None:
        result = await self._session.execute(
            select(SalesChannelModel).where(SalesChannelModel.channel_id == channel_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, store_id: UUID, name: str) -> SalesChannelModel | None:
        result = await self._session.execute(
            select(SalesChannelModel).where(
                SalesChannelModel.store_id == store_id,
                SalesChannelModel.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def save(self, channel: SalesChannelModel) -> None:
        self._session.add(channel)
        await self._session.flush()

    async def delete(self, channel: SalesChannelModel) -> None:
        await self._session.delete(channel)
        await self._session.flush()