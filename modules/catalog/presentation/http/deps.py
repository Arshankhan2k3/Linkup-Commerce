from __future__ import annotations

from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SqlAlchemyUnitOfWork, get_uow
from modules.catalog.application.services.catalog_service import CatalogApplicationService
from modules.catalog.infrastructure.db.query_services import CatalogQueryService
from modules.catalog.infrastructure.db.repositories import CatalogRepository
from modules.catalog.infrastructure.providers.media_provider import LocalMediaStorageProvider

DEFAULT_DEV_STORE_ID = UUID("00000000-0000-0000-0000-000000000001")
async def get_db_session(uow: SqlAlchemyUnitOfWork = Depends(get_uow)):
    async with uow:
        yield uow.session
        await uow.commit()



async def get_catalog_repository(
    session: AsyncSession = Depends(get_db_session),
) -> CatalogRepository:
    return CatalogRepository(session)


async def get_query_service(
    session: AsyncSession = Depends(get_db_session),
) -> CatalogQueryService:
    return CatalogQueryService(session)


async def get_media_provider() -> LocalMediaStorageProvider:
    return LocalMediaStorageProvider()


async def get_catalog_service(
    repository: CatalogRepository = Depends(get_catalog_repository),
    media_provider: LocalMediaStorageProvider = Depends(get_media_provider),
) -> CatalogApplicationService:
    return CatalogApplicationService(repository, media_provider)


async def get_storefront_store_id(
    x_store_id: str | None = Header(None, alias="X-Store-ID"),
    store_id: str | None = None,
) -> UUID:
    if x_store_id:
        try:
            return UUID(x_store_id)
        except ValueError:
            pass
    if store_id:
        try:
            return UUID(store_id)
        except ValueError:
            pass
    return DEFAULT_DEV_STORE_ID


async def get_admin_store_id(
    request: Request,
    x_store_id: str | None = Header(None, alias="X-Store-ID"),
) -> UUID:
    # Check if IAM authentication payload exists in request state
    if hasattr(request.state, "user") and isinstance(request.state.user, dict):
        s_id = request.state.user.get("store_id")
        if s_id:
            return UUID(str(s_id))

    if x_store_id:
        try:
            return UUID(x_store_id)
        except ValueError:
            pass

    return DEFAULT_DEV_STORE_ID


def require_permission(permission_code: str):
    """Dependency factory checking permissions."""
    async def _check(request: Request) -> None:
        if hasattr(request.state, "user") and isinstance(request.state.user, dict):
            perms = request.state.user.get("permissions", [])
            if permission_code not in perms:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission required: {permission_code}",
                )
    return _check