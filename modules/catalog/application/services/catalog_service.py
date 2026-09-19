from __future__ import annotations

from uuid import UUID

from modules.catalog.application.commands.collection_commands import (
    execute_create_collection,
    execute_replace_collection_products,
    execute_update_collection,
)
from modules.catalog.application.commands.media_commands import (
    execute_complete_media,
    execute_create_media_session,
    execute_replace_product_media,
)
from modules.catalog.application.commands.metafield_commands import (
    execute_create_metafield_definition,
    execute_upsert_metafields,
)
from modules.catalog.application.commands.product_commands import (
    execute_archive_product,
    execute_create_product,
    execute_delete_product,
    execute_publish_product,
    execute_update_product,
)
from modules.catalog.application.commands.tag_commands import execute_replace_product_tags
from modules.catalog.application.commands.variant_commands import (
    execute_bulk_variants,
    execute_create_option,
    execute_create_variant,
    execute_update_option,
    execute_update_variant,
)
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
from modules.catalog.application.ports.providers import IMediaStorageProvider
from modules.catalog.application.ports.services import ICatalogApplicationService
from modules.catalog.infrastructure.db.repositories import CatalogRepository


class CatalogApplicationService(ICatalogApplicationService):
    """Application orchestrator service for the Catalog domain module."""

    def __init__(
        self,
        repository: CatalogRepository,
        media_provider: IMediaStorageProvider,
    ) -> None:
        self.repository = repository
        self.media_provider = media_provider

    async def create_product(self, input_dto: CreateProductInput) -> ProductDTO:
        dto, _ = await execute_create_product(self.repository, input_dto)
        if input_dto.tags:
            await execute_replace_product_tags(self.repository, input_dto.store_id, dto.product_id, input_dto.tags)
        return dto

    async def update_product(self, input_dto: UpdateProductInput) -> ProductDTO:
        dto, _ = await execute_update_product(self.repository, input_dto)
        return dto

    async def publish_product(
        self, store_id: UUID, product_id: UUID, published_at: str | None = None
    ) -> ProductDTO:
        dto, _ = await execute_publish_product(self.repository, store_id, product_id, published_at)
        return dto

    async def archive_product(self, store_id: UUID, product_id: UUID) -> ProductDTO:
        dto, _ = await execute_archive_product(self.repository, store_id, product_id)
        return dto

    async def delete_product(self, store_id: UUID, product_id: UUID) -> None:
        await execute_delete_product(self.repository, store_id, product_id)

    async def create_option(self, input_dto: CreateOptionInput) -> OptionDTO:
        return await execute_create_option(self.repository, input_dto)

    async def update_option(self, input_dto: UpdateOptionInput) -> OptionDTO:
        return await execute_update_option(self.repository, input_dto)

    async def create_variant(self, input_dto: CreateVariantInput) -> VariantDTO:
        dto, _ = await execute_create_variant(self.repository, input_dto)
        return dto

    async def update_variant(self, input_dto: UpdateVariantInput) -> VariantDTO:
        dto, _ = await execute_update_variant(self.repository, input_dto)
        return dto

    async def bulk_create_update_variants(
        self, store_id: UUID, product_id: UUID, items: list[BulkVariantItemInput]
    ) -> list[VariantDTO]:
        return await execute_bulk_variants(self.repository, store_id, product_id, items)

    async def create_media_session(self, input_dto: CreateMediaSessionInput) -> MediaUploadSessionDTO:
        return await execute_create_media_session(self.repository, self.media_provider, input_dto)

    async def complete_media(self, input_dto: CompleteMediaInput) -> MediaAssetDTO:
        dto, _ = await execute_complete_media(self.repository, input_dto)
        return dto

    async def replace_product_media(
        self, store_id: UUID, product_id: UUID, items: list[ProductMediaItemInput]
    ) -> list[ProductMediaDTO]:
        return await execute_replace_product_media(self.repository, store_id, product_id, items)

    async def create_collection(self, input_dto: CreateCollectionInput) -> CollectionDTO:
        return await execute_create_collection(self.repository, input_dto)

    async def update_collection(self, input_dto: UpdateCollectionInput) -> CollectionDTO:
        dto, _ = await execute_update_collection(self.repository, input_dto)
        return dto

    async def replace_collection_products(
        self, store_id: UUID, collection_id: UUID, product_ids: list[UUID]
    ) -> list[UUID]:
        return await execute_replace_collection_products(self.repository, store_id, collection_id, product_ids)

    async def replace_product_tags(
        self, store_id: UUID, product_id: UUID, tag_names: list[str]
    ) -> list[TagDTO]:
        return await execute_replace_product_tags(self.repository, store_id, product_id, tag_names)

    async def create_metafield_definition(
        self, input_dto: CreateMetafieldDefinitionInput
    ) -> MetafieldDefinitionDTO:
        return await execute_create_metafield_definition(self.repository, input_dto)

    async def upsert_metafields(
        self, store_id: UUID, resource_type: str, resource_id: UUID, items: list[MetafieldItemInput]
    ) -> list[MetafieldDTO]:
        return await execute_upsert_metafields(self.repository, store_id, resource_type, resource_id, items)
