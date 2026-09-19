from __future__ import annotations

from typing import Any
from uuid import UUID

from modules.catalog.application.dto.outputs import (
    CollectionDTO,
    MetafieldDefinitionDTO,
    OptionDTO,
    OptionValueDTO,
    ProductDTO,
    ProductMediaDTO,
    SuggestionDTO,
    TagDTO,
    VariantDTO,
)
from modules.catalog.domain.exceptions import CollectionNotFoundError, ProductNotFoundError
from modules.catalog.infrastructure.db.query_services import CatalogQueryService, PaginatedResult


async def query_storefront_products(
    query_service: CatalogQueryService,
    store_id: UUID,
    first: int = 20,
    after: str | None = None,
    query: str | None = None,
    collection_slug: str | None = None,
    tag_name: str | None = None,
    sort: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
) -> PaginatedResult[ProductDTO]:
    return await query_service.list_storefront_products(
        store_id=store_id,
        first=first,
        after=after,
        query=query,
        collection_slug=collection_slug,
        tag_name=tag_name,
        sort=sort,
        min_price=min_price,
        max_price=max_price,
    )


async def query_storefront_product_detail(
    query_service: CatalogQueryService,
    store_id: UUID,
    handle: str,
) -> dict[str, Any]:
    detail = await query_service.get_storefront_product_detail(store_id, handle)
    if not detail:
        raise ProductNotFoundError(f"Product handle '{handle}' not found")
    return detail


async def query_storefront_collections(
    query_service: CatalogQueryService,
    store_id: UUID,
    first: int = 20,
    after: str | None = None,
) -> PaginatedResult[CollectionDTO]:
    return await query_service.list_storefront_collections(
        store_id=store_id,
        first=first,
        after=after,
    )
async def query_storefront_collection_detail(
    query_service: CatalogQueryService,
    store_id: UUID,
    handle: str,
    first: int = 20,
    after: str | None = None,
    sort: str | None = None,
) -> dict[str, Any]:
    detail = await query_service.get_storefront_collection_detail(
        store_id=store_id,
        handle=handle,
        first=first,
        after=after,
        sort=sort,
    )
    if not detail:
        raise CollectionNotFoundError(f"Collection handle '{handle}' not found")
    return detail


async def query_storefront_suggestions(
    query_service: CatalogQueryService,
    store_id: UUID,
    q: str,
    limit: int = 10,
) -> list[SuggestionDTO]:
    if len(q.strip()) < 2:
        return []
    return await query_service.get_suggestions(store_id=store_id, query=q, limit=min(limit, 10))


async def query_admin_products(
    query_service: CatalogQueryService,
    store_id: UUID,
    first: int = 20,
    after: str | None = None,
    query: str | None = None,
    status: str | None = None,
    vendor: str | None = None,
    tag: str | None = None,
) -> PaginatedResult[ProductDTO]:
    return await query_service.list_admin_products(
        store_id=store_id,
        first=first,
        after=after,
        query=query,
        status=status,
        vendor=vendor,
        tag=tag,
    )


async def query_admin_product_detail(
    query_service: CatalogQueryService,
    store_id: UUID,
    product_id: UUID,
) -> dict[str, Any]:
    detail = await query_service.get_admin_product_detail(store_id, product_id)
    if not detail:
        raise ProductNotFoundError(f"Product '{product_id}' not found")
    return detail


async def query_admin_collections(
    query_service: CatalogQueryService,
    store_id: UUID,
    first: int = 20,
    after: str | None = None,
    query: str | None = None,
    status: str | None = None,
) -> PaginatedResult[CollectionDTO]:
    return await query_service.list_admin_collections(
        store_id=store_id,
        first=first,
        after=after,
        query=query,
        status=status,
    )


async def query_admin_metafield_definitions(
    query_service: CatalogQueryService,
    store_id: UUID,
    resource_type: str | None = None,
) -> list[MetafieldDefinitionDTO]:
    return await query_service.list_metafield_definitions(store_id=store_id, resource_type=resource_type)
