from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from modules.catalog.application.dto.inputs import (
    BulkVariantItemInput,
    CompleteMediaInput,
    CreateCollectionInput,
    CreateMediaSessionInput,
    CreateMetafieldDefinitionInput,
    CreateOptionInput,
    CreateOptionValueInput,
    CreateProductInput,
    CreateVariantInput,
    MetafieldItemInput,
    ProductMediaItemInput,
    UpdateCollectionInput,
    UpdateOptionInput,
    UpdateProductInput,
    UpdateVariantInput,
)
from modules.catalog.application.queries.catalog_queries import (
    query_admin_collections,
    query_admin_metafield_definitions,
    query_admin_product_detail,
    query_admin_products,
)
from modules.catalog.application.services.catalog_service import CatalogApplicationService
from modules.catalog.domain.exceptions import (
    CatalogError,
    CollectionAlreadyExistsError,
    CollectionNotFoundError,
    ConcurrencyError,
    DuplicateSKUError,
    InvalidProductError,
    MediaNotFoundError,
    MetafieldDefinitionNotFoundError,
    MetafieldValidationError,
    ProductAlreadyExistsError,
    ProductNotFoundError,
    PublishProductValidationError,
    VariantAlreadyExistsError,
    VariantNotFoundError,
)
from modules.catalog.infrastructure.db.query_services import CatalogQueryService
from modules.catalog.presentation.http.deps import (
    get_admin_store_id,
    get_catalog_service,
    get_query_service,
    require_permission,
)
from modules.catalog.presentation.http.schemas.common import Connection
from modules.catalog.presentation.http.schemas.requests import (
    BulkVariantRequest,
    CollectionPatchRequest,
    CollectionProductsReplaceRequest,
    CreateCollectionRequest,
    CreateMetafieldDefinitionRequest,
    CreateOptionRequest,
    CreateVariantRequest,
    FinalizeMediaRequest,
    MediaUploadSessionRequest,
    MetafieldUpsertItem,
    PatchOptionRequest,
    PatchVariantRequest,
    ProductCreateRequest,
    ProductPatchRequest,
    PublishProductRequest,
    ReplaceProductMediaRequest,
    ReplaceProductTagsRequest,
    UpsertMetafieldsRequest,
)
from modules.catalog.presentation.http.schemas.responses import (
    AdminProductDetailResponse,
    BulkVariantResult,
    CollectionResponse,
    MediaAssetResponse,
    MediaUploadSessionResponse,
    MetafieldDefinitionResponse,
    MetafieldResponse,
    ProductMediaResponse,
    ProductOptionResponse,
    ProductResponse,
    TagResponse,
    VariantResponse,
)

router = APIRouter(prefix="/admin", tags=["Catalog Admin"])


def _handle_domain_error(exc: CatalogError) -> None:
    if isinstance(exc, (ProductNotFoundError, VariantNotFoundError, CollectionNotFoundError, MetafieldDefinitionNotFoundError, MediaNotFoundError)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    elif isinstance(exc, (ProductAlreadyExistsError, CollectionAlreadyExistsError, VariantAlreadyExistsError, DuplicateSKUError)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    elif isinstance(exc, ConcurrencyError):
        raise HTTPException(status_code=status.HTTP_412_PRECONDITION_FAILED, detail=str(exc))
    elif isinstance(exc, (PublishProductValidationError, MetafieldValidationError, InvalidProductError)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# 6. P0: GET /api/v1/admin/products
@router.get(
    "/products",
    response_model=Connection[ProductResponse],
    dependencies=[Depends(require_permission("products.read"))],
)
async def list_admin_products(
    first: int = Query(20, ge=1, le=100),
    after: str | None = None,
    query: str | None = None,
    status: str | None = None,
    vendor: str | None = None,
    tag: str | None = None,
    store_id: UUID = Depends(get_admin_store_id),
    query_service: CatalogQueryService = Depends(get_query_service),
) -> Any:
    return await query_admin_products(
        query_service=query_service,
        store_id=store_id,
        first=first,
        after=after,
        query=query,
        status=status,
        vendor=vendor,
        tag=tag,
    )


# 7. P0: POST /api/v1/admin/products
@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("products.write"))],
)
async def create_product(
    body: ProductCreateRequest,
    store_id: UUID = Depends(get_admin_store_id),
    service: CatalogApplicationService = Depends(get_catalog_service),
) -> Any:
    try:
        input_dto = CreateProductInput(
            store_id=store_id,
            title=body.title,
            slug=body.handle,
            description_html=body.description,
            vendor=body.vendor,
            product_type=body.product_type,
            status=body.status,
            requires_shipping=body.requires_shipping,
            taxable=body.taxable,
            tags=body.tags,
        )
        return await service.create_product(input_dto)
    except CatalogError as exc:
        _handle_domain_error(exc)


# 8. P0: GET /api/v1/admin/products/{product_id}
@router.get(
    "/products/{product_id}",
    response_model=AdminProductDetailResponse,
    dependencies=[Depends(require_permission("products.read"))],
)
async def get_admin_product_detail(
    product_id: UUID,
    store_id: UUID = Depends(get_admin_store_id),
    query_service: CatalogQueryService = Depends(get_query_service),
) -> Any:
    try:
        return await query_admin_product_detail(query_service, store_id, product_id)
    except CatalogError as exc:
        _handle_domain_error(exc)


# 9. P0: PATCH /api/v1/admin/products/{product_id}
@router.patch(
    "/products/{product_id}",
    response_model=ProductResponse,
    dependencies=[Depends(require_permission("products.write"))],
)
async def update_product(
    product_id: UUID,
    body: ProductPatchRequest,
    store_id: UUID = Depends(get_admin_store_id),
    service: CatalogApplicationService = Depends(get_catalog_service),
) -> Any:
    try:
        input_dto = UpdateProductInput(
            store_id=store_id,
            product_id=product_id,
            title=body.title,
            slug=body.handle,
            description_html=body.description,
            vendor=body.vendor,
            product_type=body.product_type,
            status=body.status,
            requires_shipping=body.requires_shipping,
            taxable=body.taxable,
            version=body.version,
        )
        return await service.update_product(input_dto)
    except CatalogError as exc:
        _handle_domain_error(exc)


# 10. P0: POST /api/v1/admin/products/{product_id}/publish
@router.post(
    "/products/{product_id}/publish",
    response_model=ProductResponse,
    dependencies=[Depends(require_permission("products.publish"))],
)
async def publish_product(
    product_id: UUID,
    body: PublishProductRequest | None = None,
    store_id: UUID = Depends(get_admin_store_id),
    service: CatalogApplicationService = Depends(get_catalog_service),
) -> Any:
    try:
        published_at = body.published_at if body else None
        return await service.publish_product(store_id, product_id, published_at)
    except CatalogError as exc:
        _handle_domain_error(exc)


# 11. P0: POST /api/v1/admin/products/{product_id}/archive
@router.post(
    "/products/{product_id}/archive",
    response_model=ProductResponse,
    dependencies=[Depends(require_permission("products.write"))],
)
async def archive_product(
    product_id: UUID,
    store_id: UUID = Depends(get_admin_store_id),
    service: CatalogApplicationService = Depends(get_catalog_service),
) -> Any:
    try:
        return await service.archive_product(store_id, product_id)
    except CatalogError as exc:
        _handle_domain_error(exc)


# 12. P1: DELETE /api/v1/admin/products/{product_id}
@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("products.delete"))],
)
async def delete_product(
    product_id: UUID,
    store_id: UUID = Depends(get_admin_store_id),
    service: CatalogApplicationService = Depends(get_catalog_service),
) -> None:
    try:
        await service.delete_product(store_id, product_id)
    except CatalogError as exc:
        _handle_domain_error(exc)


# 13. P0: POST /api/v1/admin/products/{product_id}/options
@router.post(
    "/products/{product_id}/options",
    response_model=ProductOptionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("products.write"))],
)
async def create_product_option(
    product_id: UUID,
    body: CreateOptionRequest,
    service: CatalogApplicationService = Depends(get_catalog_service),
) -> Any:
    try:
        vals = [
            CreateOptionValueInput(value=v.value, position=v.position, metadata=v.metadata)
            for v in body.values
        ]
        input_dto = CreateOptionInput(
            product_id=product_id,
            name=body.name,
            position=body.position,
            values=vals,
        )
        return await service.create_option(input_dto)
    except CatalogError as exc:
        _handle_domain_error(exc)


# 14. P1: PATCH /api/v1/admin/products/{product_id}/options/{option_id}
@router.patch(
    "/products/{product_id}/options/{option_id}",
    response_model=ProductOptionResponse,
    dependencies=[Depends(require_permission("products.write"))],
)
async def update_product_option(
    product_id: UUID,
    option_id: UUID,
    body: PatchOptionRequest,
    service: CatalogApplicationService = Depends(get_catalog_service),
) -> Any:
    try:
        vals = None
        if body.values is not None:
            vals = [
                CreateOptionValueInput(value=v.value, position=v.position, metadata=v.metadata)
                for v in body.values
            ]
        input_dto = UpdateOptionInput(
            product_id=product_id,
            option_id=option_id,
            name=body.name,
            position=body.position,
            values=vals,
        )
        return await service.update_option(input_dto)
    except CatalogError as exc:
        _handle_domain_error(exc)


# 15. P0: POST /api/v1/admin/products/{product_id}/variants
@router.post(
    "/products/{product_id}/variants",
    response_model=VariantResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("products.write"))],
)
async def create_variant(
    product_id: UUID,
    body: CreateVariantRequest,
    store_id: UUID = Depends(get_admin_store_id),
    service: CatalogApplicationService = Depends(get_catalog_service),
) -> Any:
    try:
        input_dto = CreateVariantInput(
            store_id=store_id,
            product_id=product_id,
            base_price=body.price,
            sku=body.sku,
            barcode=body.barcode,
            option_value_ids=body.option_value_ids,
            compare_at_price=body.compare_at_price,
            cost_price=body.cost_price,
            weight=body.weight,
            weight_unit=body.weight_unit,
            length=body.length,
            width=body.width,
            height=body.height,
            dimension_unit=body.dimension_unit,
            is_active=body.is_active,
        )
        return await service.create_variant(input_dto)
    except CatalogError as exc:
        _handle_domain_error(exc)


# 16. P1: POST /api/v1/admin/products/{product_id}/variants/bulk
@router.post(
    "/products/{product_id}/variants/bulk",
    response_model=BulkVariantResult,
    dependencies=[Depends(require_permission("products.write"))],
)
async def bulk_variants(
    product_id: UUID,
    body: BulkVariantRequest,
    store_id: UUID = Depends(get_admin_store_id),
    service: CatalogApplicationService = Depends(get_catalog_service),
) -> Any:
    try:
        items = [
            BulkVariantItemInput(
                variant_id=item.variant_id,
                sku=item.sku,
                barcode=item.barcode,
                base_price=item.price,
                option_value_ids=item.option_value_ids,
                compare_at_price=item.compare_at_price,
                is_active=item.is_active,
            )
            for item in body.items
        ]
        res_items = await service.bulk_create_update_variants(store_id, product_id, items)
        return BulkVariantResult(items=res_items)
    except CatalogError as exc:
        _handle_domain_error(exc)


# 17. P0: PATCH /api/v1/admin/variants/{variant_id}
@router.patch(
    "/variants/{variant_id}",
    response_model=VariantResponse,
    dependencies=[Depends(require_permission("products.write"))],
)
async def update_variant(
    variant_id: UUID,
    body: PatchVariantRequest,
    store_id: UUID = Depends(get_admin_store_id),
    service: CatalogApplicationService = Depends(get_catalog_service),
) -> Any:
    try:
        input_dto = UpdateVariantInput(
            store_id=store_id,
            variant_id=variant_id,
            sku=body.sku,
            barcode=body.barcode,
            base_price=body.price,
            compare_at_price=body.compare_at_price,
            cost_price=body.cost_price,
            weight=body.weight,
            weight_unit=body.weight_unit,
            is_active=body.is_active,
            version=body.version,
        )
        return await service.update_variant(input_dto)
    except CatalogError as exc:
        _handle_domain_error(exc)


# 18. P0: POST /api/v1/admin/media
@router.post(
    "/media",
    response_model=MediaUploadSessionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("media.write"))],
)
async def create_media_session(
    body: MediaUploadSessionRequest,
    store_id: UUID = Depends(get_admin_store_id),
    service: CatalogApplicationService = Depends(get_catalog_service),
) -> Any:
    try:
        input_dto = CreateMediaSessionInput(
            store_id=store_id,
            filename=body.filename,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
            checksum=body.checksum,
        )
        return await service.create_media_session(input_dto)
    except CatalogError as exc:
        _handle_domain_error(exc)


# 19. P0: POST /api/v1/admin/media/{media_id}/complete
@router.post(
    "/media/{media_id}/complete",
    response_model=MediaAssetResponse,
    dependencies=[Depends(require_permission("media.write"))],
)
async def complete_media(
    media_id: UUID,
    body: FinalizeMediaRequest,
    store_id: UUID = Depends(get_admin_store_id),
    service: CatalogApplicationService = Depends(get_catalog_service),
) -> Any:
    try:
        input_dto = CompleteMediaInput(
            store_id=store_id,
            media_id=media_id,
            checksum=body.checksum,
            width=body.width,
            height=body.height,
        )
        return await service.complete_media(input_dto)
    except CatalogError as exc:
        _handle_domain_error(exc)


# 20. P1: PUT /api/v1/admin/products/{product_id}/media
@router.put(
    "/products/{product_id}/media",
    response_model=list[ProductMediaResponse],
    dependencies=[Depends(require_permission("products.write"))],
)
async def replace_product_media(
    product_id: UUID,
    body: ReplaceProductMediaRequest,
    store_id: UUID = Depends(get_admin_store_id),
    service: CatalogApplicationService = Depends(get_catalog_service),
) -> Any:
    try:
        items = body.items
        if not items and body.media_ids:
            items = [
                ProductMediaLinkItem(
                    media_id=mid,
                    position=idx,
                    is_primary=(mid == body.featured_media_id or idx == 0),
                )
                for idx, mid in enumerate(body.media_ids)
            ]

        dto_items = [
            ProductMediaItemInput(
                media_id=it.media_id,
                position=it.position,
                is_primary=it.is_primary,
                variant_id=it.variant_id,
            )
            for it in items
        ]

        return await service.replace_product_media(store_id, product_id, dto_items)
    except CatalogError as exc:
        _handle_domain_error(exc)


# 21. P1: GET /api/v1/admin/collections
@router.get(
    "/collections",
    response_model=Connection[CollectionResponse],
    dependencies=[Depends(require_permission("collections.read"))],
)
async def list_admin_collections(
    first: int = Query(20, ge=1, le=100),
    after: str | None = None,
    query: str | None = None,
    status: str | None = None,
    store_id: UUID = Depends(get_admin_store_id),
    query_service: CatalogQueryService = Depends(get_query_service),
) -> Any:
    return await query_admin_collections(
        query_service=query_service,
        store_id=store_id,
        first=first,
        after=after,
        query=query,
        status=status,
    )


# 22. P1: POST /api/v1/admin/collections
@router.post(
    "/collections",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("collections.write"))],
)
async def create_collection(
    body: CreateCollectionRequest,
    store_id: UUID = Depends(get_admin_store_id),
    service: CatalogApplicationService = Depends(get_catalog_service),
) -> Any:
    try:
        input_dto = CreateCollectionInput(
            store_id=store_id,
            title=body.title,
            slug=body.handle,
            description_html=body.description,
            collection_type=body.collection_type,
            rule_json=body.rule_json,
            status=body.status,
        )
        return await service.create_collection(input_dto)
    except CatalogError as exc:
        _handle_domain_error(exc)


# 23. P1: PATCH /api/v1/admin/collections/{collection_id}
@router.patch(
    "/collections/{collection_id}",
    response_model=CollectionResponse,
    dependencies=[Depends(require_permission("collections.write"))],
)
async def update_collection(
    collection_id: UUID,
    body: CollectionPatchRequest,
    store_id: UUID = Depends(get_admin_store_id),
    service: CatalogApplicationService = Depends(get_catalog_service),
) -> Any:
    try:
        input_dto = UpdateCollectionInput(
            store_id=store_id,
            collection_id=collection_id,
            title=body.title,
            slug=body.handle,
            description_html=body.description,
            status=body.status,
            rule_json=body.rule_json,
        )
        return await service.update_collection(input_dto)
    except CatalogError as exc:
        _handle_domain_error(exc)


# 24. P1: PUT /api/v1/admin/collections/{collection_id}/products
@router.put(
    "/collections/{collection_id}/products",
    response_model=dict[str, list[UUID]],
    dependencies=[Depends(require_permission("collections.write"))],
)
async def replace_collection_products(
    collection_id: UUID,
    body: CollectionProductsReplaceRequest,
    store_id: UUID = Depends(get_admin_store_id),
    service: CatalogApplicationService = Depends(get_catalog_service),
) -> Any:
    try:
        p_ids = await service.replace_collection_products(store_id, collection_id, body.product_ids)
        return {"product_ids": p_ids}
    except CatalogError as exc:
        _handle_domain_error(exc)


# 25. P1: PUT /api/v1/admin/products/{product_id}/tags
@router.put(
    "/products/{product_id}/tags",
    response_model=list[TagResponse],
    dependencies=[Depends(require_permission("products.write"))],
)
async def replace_product_tags(
    product_id: UUID,
    body: ReplaceProductTagsRequest,
    store_id: UUID = Depends(get_admin_store_id),
    service: CatalogApplicationService = Depends(get_catalog_service),
) -> Any:
    try:
        return await service.replace_product_tags(store_id, product_id, body.tags)
    except CatalogError as exc:
        _handle_domain_error(exc)


# 26. P2: GET /api/v1/admin/metafield-definitions
@router.get(
    "/metafield-definitions",
    response_model=list[MetafieldDefinitionResponse],
    dependencies=[Depends(require_permission("metafields.read"))],
)
async def list_metafield_definitions(
    owner_type: str | None = None,
    store_id: UUID = Depends(get_admin_store_id),
    query_service: CatalogQueryService = Depends(get_query_service),
) -> Any:
    return await query_admin_metafield_definitions(query_service, store_id, owner_type)


# 27. P2: POST /api/v1/admin/metafield-definitions
@router.post(
    "/metafield-definitions",
    response_model=MetafieldDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("metafields.write"))],
)
async def create_metafield_definition(
    body: CreateMetafieldDefinitionRequest,
    store_id: UUID = Depends(get_admin_store_id),
    service: CatalogApplicationService = Depends(get_catalog_service),
) -> Any:
    try:
        input_dto = CreateMetafieldDefinitionInput(
            store_id=store_id,
            resource_type=body.owner_type,
            namespace=body.namespace,
            key=body.key,
            value_type=body.data_type,
            validation=body.validation,
        )
        return await service.create_metafield_definition(input_dto)
    except CatalogError as exc:
        _handle_domain_error(exc)


# 28. P2: PUT /api/v1/admin/{owner_type}/{owner_id}/metafields
@router.put(
    "/{owner_type}/{owner_id}/metafields",
    response_model=list[MetafieldResponse],
    dependencies=[Depends(require_permission("metafields.write"))],
)
async def upsert_metafields(
    owner_type: str,
    owner_id: UUID,
    body: UpsertMetafieldsRequest,
    store_id: UUID = Depends(get_admin_store_id),
    service: CatalogApplicationService = Depends(get_catalog_service),
) -> Any:
    try:
        items = [MetafieldItemInput(definition_id=it.definition_id, value=it.value) for it in body.values]
        return await service.upsert_metafields(store_id, owner_type, owner_id, items)
    except CatalogError as exc:
        _handle_domain_error(exc)