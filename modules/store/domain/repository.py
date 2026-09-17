"""Abstract repository protocols for the Store domain."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from modules.store.domain.entities import SalesChannel, Store, StoreSettings


class StoreRepository(Protocol):
    async def get_by_id(self, store_id: UUID) -> Store | None:
        ...

    async def get_first_active_store(self) -> Store | None:
        ...

    async def save(self, store: Store) -> None:
        ...
    
class StoreSettingsRepository(Protocol):
    async def get_by_store(self, store_id: UUID) -> StoreSettings | None:
        ...

    async def save(self, settings: StoreSettings) -> None:
        ...
        
class SalesChannelRepository(Protocol):
    async def list_by_store(
        self,
        store_id: UUID,
        first: int = 25,
        after: str | None = None,
        status: str | None = None,
    ) -> list[SalesChannel]:
        ...

    async def get_by_id(self, channel_id: UUID) -> SalesChannel | None:
        ...

    async def get_by_name(self, store_id: UUID, name: str) -> SalesChannel | None:
        ...

    async def save(self, channel: SalesChannel) -> None:
        ...

    async def delete(self, channel: SalesChannel) -> None:
        ...
