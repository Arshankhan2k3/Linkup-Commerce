from __future__ import annotations

from typing import Protocol
from uuid import UUID

from modules.catalog.application.dto.inputs import (
    BulkVariantItemInput,
    CompleteMediaInput,
    CreateCollectionInput,
    CreateMediaSessionInput,
    CreateMetafieldDefinitionInput,
    CreateOptionInput,
    CreateProductInput,
    CreateVariantInput,
    MetafieldItemInput,
    ProductMediaItemInput,
    UpdateCollectionInput,
    UpdateOptionInput,
    UpdateProductInput,
    UpdateVariantInput,
)
from modules.catalog.application.dto.outputs import (
    CollectionDTO,
    MediaAssetDTO,
    MediaUploadSessionDTO,
    MetafieldDefinitionDTO,
    MetafieldDTO,
    OptionDTO,
    ProductDTO,
    ProductMediaDTO,
    TagDTO,
    VariantDTO,
)


class ICatalogApplicationService(Protocol):
    """Protocol for Catalog Orchestrator Service."""

    async def create_product(self, input_dto: CreateProductInput) -> ProductDTO: ...
    async def update_product(self, input_dto: UpdateProductInput) -> ProductDTO: ...
    async def publish_product(self, store_id: UUID, product_id: UUID, published_at: str | None = None) -> ProductDTO: ...
    async def archive_product(self, store_id: UUID, product_id: UUID) -> ProductDTO: ...
    async def delete_product(self, store_id: UUID, product_id: UUID) -> None: ...

    async def create_option(self, input_dto: CreateOptionInput) -> OptionDTO: ...
    async def update_option(self, input_dto: UpdateOptionInput) -> OptionDTO: ...

    async def create_variant(self, input_dto: CreateVariantInput) -> VariantDTO: ...
    async def update_variant(self, input_dto: UpdateVariantInput) -> VariantDTO: ...
    async def bulk_create_update_variants(
        self, store_id: UUID, product_id: UUID, items: list[BulkVariantItemInput]
    ) -> list[VariantDTO]: ...

    async def create_media_session(self, input_dto: CreateMediaSessionInput) -> MediaUploadSessionDTO: ...
    async def complete_media(self, input_dto: CompleteMediaInput) -> MediaAssetDTO: ...
    async def replace_product_media(
        self, store_id: UUID, product_id: UUID, items: list[ProductMediaItemInput]
    ) -> list[ProductMediaDTO]: ...

    async def create_collection(self, input_dto: CreateCollectionInput) -> CollectionDTO: ...
    async def update_collection(self, input_dto: UpdateCollectionInput) -> CollectionDTO: ...
    async def replace_collection_products(
        self, store_id: UUID, collection_id: UUID, product_ids: list[UUID]
    ) -> list[UUID]: ...

    async def replace_product_tags(
        self, store_id: UUID, product_id: UUID, tag_names: list[str]
    ) -> list[TagDTO]: ...

    async def create_metafield_definition(
        self, input_dto: CreateMetafieldDefinitionInput
    ) -> MetafieldDefinitionDTO: ...
    async def upsert_metafields(
        self, store_id: UUID, resource_type: str, resource_id: UUID, items: list[MetafieldItemInput]
    ) -> list[MetafieldDTO]: ...
