"""Database session factory + SqlAlchemy Unit of Work implementation.

``SqlAlchemyUnitOfWork`` implements the ``UnitOfWork`` protocol defined in
``shared/application/unit_of_work.py``.  It is the **only** place in the
application that calls ``session.commit()`` or ``session.rollback()``.

Routes and services MUST use the UoW as an async context manager:

    async with SqlAlchemyUnitOfWork() as uow:
        repo = SomeRepository(uow.session)
        await repo.save(entity)
        await uow.commit()

FastAPI dependency ``get_uow`` is provided for route injection.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# ---------------------------------------------------------------------------
# Engine + session factory
# ---------------------------------------------------------------------------

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    # Return connection to pool after each transaction commit/rollback.
    pool_pre_ping=True,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# Unit of Work
# ---------------------------------------------------------------------------

class SqlAlchemyUnitOfWork:
    """Concrete implementation of the UnitOfWork protocol.

    Lifecycle
    ---------
    1. ``__aenter__`` — open a new ``AsyncSession``.
    2. Use ``self.session`` to build repositories.
    3. ``commit()`` — flush + commit the transaction.
    4. Any exception inside the ``async with`` block triggers ``rollback()``.
    5. ``__aexit__`` — always closes the session.

    Never expose ``self.session`` outside the UoW boundary.
    """

    def __init__(self) -> None:
        self._session: AsyncSession | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError(
                "SqlAlchemyUnitOfWork.session accessed outside of context manager"
            )
        return self._session

    async def __aenter__(self) -> Self:
        self._session = AsyncSessionLocal()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def commit(self) -> None:
        """Flush pending changes and commit the transaction."""
        if self._session is None:
            raise RuntimeError("commit() called outside of context manager")
        await self._session.commit()

    async def rollback(self) -> None:
        """Roll back the current transaction."""
        if self._session is None:
            return
        await self._session.rollback()


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_uow() -> AsyncGenerator[SqlAlchemyUnitOfWork, None]:
    """Yield a fresh UnitOfWork for each request.

    Usage in routes::

        @router.post("/...")
        async def my_route(uow: SqlAlchemyUnitOfWork = Depends(get_uow)):
            async with uow:
                ...
                await uow.commit()
    """
    uow = SqlAlchemyUnitOfWork()
    try:
        yield uow
    finally:
        pass  # Lifecycle is managed by the route via `async with uow`