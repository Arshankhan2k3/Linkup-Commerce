from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from modules.catalog.application.queries.catalog_queries import (
    query_storefront_collection_detail,
    query_storefront_collections,
    query_storefront_product_detail,
    query_storefront_products,
    query_storefront_suggestions,
)
from modules.catalog.domain.exceptions import CollectionNotFoundError, ProductNotFoundError
from modules.catalog.infrastructure.db.query_services import CatalogQueryService
from modules.catalog.presentation.http.deps import get_query_service, get_storefront_store_id
from modules.catalog.presentation.http.schemas.common import Connection
from modules.catalog.presentation.http.schemas.responses import (
    CollectionDetailResponse,
    CollectionResponse,
    ProductDetailResponse,
    ProductResponse,
    SuggestionItemResponse,
    SuggestionResponse,
)

router = APIRouter(prefix="/storefront", tags=["Catalog Storefront"])


# 1. P0: GET /api/v1/storefront/products
@router.get(
    "/products",
    response_model=Connection[ProductResponse],
)
async def list_storefront_products(
    first: int = Query(20, ge=1, le=100),
    after: str | None = None,
    query: str | None = None,
    collection: str | None = None,
    tag: str | None = None,
    sort: str | None = None,
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    store_id: UUID = Depends(get_storefront_store_id),
    query_service: CatalogQueryService = Depends(get_query_service),
) -> Any:
    return await query_storefront_products(
        query_service=query_service,
        store_id=store_id,
        first=first,
        after=after,
        query=query,
        collection_slug=collection,
        tag_name=tag,
        sort=sort,
        min_price=min_price,
        max_price=max_price,
    )


# 2. P0: GET /api/v1/storefront/products/{handle}
@router.get(
    "/products/{handle}",
    response_model=ProductDetailResponse,
)
async def get_storefront_product_by_handle(
    handle: str,
    store_id: UUID = Depends(get_storefront_store_id),
    query_service: CatalogQueryService = Depends(get_query_service),
) -> Any:
    try:
        return await query_storefront_product_detail(
            query_service=query_service,
            store_id=store_id,
            handle=handle,
        )
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


# 3. P1: GET /api/v1/storefront/collections
@router.get(
    "/collections",
    response_model=Connection[CollectionResponse],
)
async def list_storefront_collections(
    first: int = Query(20, ge=1, le=100),
    after: str | None = None,
    store_id: UUID = Depends(get_storefront_store_id),
    query_service: CatalogQueryService = Depends(get_query_service),
) -> Any:
    return await query_storefront_collections(
        query_service=query_service,
        store_id=store_id,
        first=first,
        after=after,
    )


# 4. P1: GET /api/v1/storefront/collections/{handle}
@router.get(
    "/collections/{handle}",
    response_model=CollectionDetailResponse,
)
async def get_storefront_collection_by_handle(
    handle: str,
    first: int = Query(20, ge=1, le=100),
    after: str | None = None,
    sort: str | None = None,
    store_id: UUID = Depends(get_storefront_store_id),
    query_service: CatalogQueryService = Depends(get_query_service),
) -> Any:
    try:
        return await query_storefront_collection_detail(
            query_service=query_service,
            store_id=store_id,
            handle=handle,
            first=first,
            after=after,
            sort=sort,
        )
    except CollectionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


# 5. P1: GET /api/v1/storefront/search/suggestions
@router.get(
    "/search/suggestions",
    response_model=SuggestionResponse,
)
async def get_storefront_suggestions(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=10),
    store_id: UUID = Depends(get_storefront_store_id),
    query_service: CatalogQueryService = Depends(get_query_service),
) -> Any:
    suggestions = await query_storefront_suggestions(
        query_service=query_service,
        store_id=store_id,
        q=q,
        limit=limit,
    )
    return SuggestionResponse(
        suggestions=[
            SuggestionItemResponse(
                text=s.text,
                suggestion_type=s.suggestion_type,
                handle=s.handle,
                id=s.id,
            )
            for s in suggestions
        ]
    )
