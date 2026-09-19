from __future__ import annotations

from types import TracebackType
from sqlalchemy.ext.asyncio import AsyncSession

from .repositories import CatalogRepository


class CatalogUnitOfWork:
    """Unit of work pattern manager for catalog module transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = CatalogRepository(session)

    async def __aenter__(self) -> CatalogUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
