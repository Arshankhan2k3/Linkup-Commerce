from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    CollectionModel,
    CollectionProductModel,
    MediaAssetModel,
    MetafieldDefinitionModel,
    MetafieldModel,
    ProductMediaModel,
    ProductModel,
    ProductOptionModel,
    ProductOptionValueModel,
    ProductTagModel,
    ProductVariantModel,
    TagModel,
    VariantOptionValueModel,
)


class CatalogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # -------------------------
    # Products
    # -------------------------

    async def create_product(self, product: ProductModel) -> ProductModel:
        self.session.add(product)
        await self.session.flush()
        return product

    async def get_product(
        self,
        store_id: UUID,
        product_id: UUID,
    ) -> ProductModel | None:
        result = await self.session.execute(
            select(ProductModel).where(
                ProductModel.store_id == store_id,
                ProductModel.product_id == product_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_product_by_slug(
        self,
        store_id: UUID,
        slug: str,
    ) -> ProductModel | None:
        result = await self.session.execute(
            select(ProductModel).where(
                ProductModel.store_id == store_id,
                ProductModel.slug == slug,
            )
        )
        return result.scalar_one_or_none()

    async def list_products(
        self,
        store_id: UUID,
        status: str | None = None,
    ) -> list[ProductModel]:
        query = select(ProductModel).where(
            ProductModel.store_id == store_id
        )

        if status:
            query = query.where(ProductModel.status == status)

        query = query.order_by(ProductModel.created_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_product(
        self,
        store_id: UUID,
        product_id: UUID,
        values: dict,
    ) -> ProductModel | None:
        await self.session.execute(
            update(ProductModel)
            .where(
                ProductModel.store_id == store_id,
                ProductModel.product_id == product_id,
            )
            .values(**values)
        )

        return await self.get_product(store_id, product_id)

    async def delete_product(
        self,
        store_id: UUID,
        product_id: UUID,
    ) -> bool:
        result = await self.session.execute(
            delete(ProductModel).where(
                ProductModel.store_id == store_id,
                ProductModel.product_id == product_id,
            )
        )

        return result.rowcount > 0

    # -------------------------
    # Product Options
    # -------------------------

    async def create_option(
        self,
        option: ProductOptionModel,
    ) -> ProductOptionModel:
        self.session.add(option)
        await self.session.flush()
        return option

    async def get_option(
        self,
        product_id: UUID,
        option_id: UUID,
    ) -> ProductOptionModel | None:
        result = await self.session.execute(
            select(ProductOptionModel).where(
                ProductOptionModel.product_id == product_id,
                ProductOptionModel.option_id == option_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_options(
        self,
        product_id: UUID,
    ) -> list[ProductOptionModel]:
        result = await self.session.execute(
            select(ProductOptionModel)
            .where(ProductOptionModel.product_id == product_id)
            .order_by(ProductOptionModel.position)
        )
        return list(result.scalars().all())

    async def update_option(
        self,
        product_id: UUID,
        option_id: UUID,
        values: dict,
    ) -> ProductOptionModel | None:
        await self.session.execute(
            update(ProductOptionModel)
            .where(
                ProductOptionModel.product_id == product_id,
                ProductOptionModel.option_id == option_id,
            )
            .values(**values)
        )

        return await self.get_option(product_id, option_id)

    # -------------------------
    # Option Values
    # -------------------------

    async def create_option_value(
        self,
        option_value: ProductOptionValueModel,
    ) -> ProductOptionValueModel:
        self.session.add(option_value)
        await self.session.flush()
        return option_value

    async def list_option_values(
        self,
        option_id: UUID,
    ) -> list[ProductOptionValueModel]:
        result = await self.session.execute(
            select(ProductOptionValueModel)
            .where(ProductOptionValueModel.option_id == option_id)
            .order_by(ProductOptionValueModel.position)
        )
        return list(result.scalars().all())

    # -------------------------
    # Variants
    # -------------------------

    async def create_variant(
        self,
        variant: ProductVariantModel,
    ) -> ProductVariantModel:
        self.session.add(variant)
        await self.session.flush()
        return variant

    async def get_variant(
        self,
        store_id: UUID,
        variant_id: UUID,
    ) -> ProductVariantModel | None:
        result = await self.session.execute(
            select(ProductVariantModel).where(
                ProductVariantModel.store_id == store_id,
                ProductVariantModel.variant_id == variant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_variant_by_sku(
        self,
        store_id: UUID,
        sku: str,
    ) -> ProductVariantModel | None:
        result = await self.session.execute(
            select(ProductVariantModel).where(
                ProductVariantModel.store_id == store_id,
                ProductVariantModel.sku == sku,
            )
        )
        return result.scalar_one_or_none()

    async def get_variant_by_signature(
        self,
        product_id: UUID,
        option_signature: str,
    ) -> ProductVariantModel | None:
        result = await self.session.execute(
            select(ProductVariantModel).where(
                ProductVariantModel.product_id == product_id,
                ProductVariantModel.option_signature == option_signature,
            )
        )
        return result.scalar_one_or_none()

    async def list_variants(
        self,
        product_id: UUID,
    ) -> list[ProductVariantModel]:
        result = await self.session.execute(
            select(ProductVariantModel)
            .where(ProductVariantModel.product_id == product_id)
            .order_by(ProductVariantModel.position)
        )
        return list(result.scalars().all())

    async def update_variant(
        self,
        store_id: UUID,
        variant_id: UUID,
        values: dict,
    ) -> ProductVariantModel | None:
        await self.session.execute(
            update(ProductVariantModel)
            .where(
                ProductVariantModel.store_id == store_id,
                ProductVariantModel.variant_id == variant_id,
            )
            .values(**values)
        )

        return await self.get_variant(store_id, variant_id)

    # -------------------------
    # Variant Option Values
    # -------------------------

    async def add_variant_option_value(
        self,
        item: VariantOptionValueModel,
    ) -> VariantOptionValueModel:
        self.session.add(item)
        await self.session.flush()
        return item

    async def list_variant_option_values(
        self,
        variant_id: UUID,
    ) -> list[VariantOptionValueModel]:
        result = await self.session.execute(
            select(VariantOptionValueModel).where(
                VariantOptionValueModel.variant_id == variant_id
            )
        )
        return list(result.scalars().all())

    # -------------------------
    # Media
    # -------------------------

    async def create_media(
        self,
        media: MediaAssetModel,
    ) -> MediaAssetModel:
        self.session.add(media)
        await self.session.flush()
        return media

    async def get_media(
        self,
        store_id: UUID,
        media_id: UUID,
    ) -> MediaAssetModel | None:
        result = await self.session.execute(
            select(MediaAssetModel).where(
                MediaAssetModel.store_id == store_id,
                MediaAssetModel.media_id == media_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_media(
        self,
        store_id: UUID,
        media_id: UUID,
        values: dict,
    ) -> MediaAssetModel | None:
        await self.session.execute(
            update(MediaAssetModel)
            .where(
                MediaAssetModel.store_id == store_id,
                MediaAssetModel.media_id == media_id,
            )
            .values(**values)
        )

        return await self.get_media(store_id, media_id)

    # -------------------------
    # Product Media
    # -------------------------

    async def add_product_media(
        self,
        item: ProductMediaModel,
    ) -> ProductMediaModel:
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_product_media(
        self,
        product_id: UUID,
    ) -> list[ProductMediaModel]:
        result = await self.session.execute(
            select(ProductMediaModel)
            .where(ProductMediaModel.product_id == product_id)
            .order_by(ProductMediaModel.position)
        )
        return list(result.scalars().all())

    async def delete_product_media(
        self,
        product_id: UUID,
    ) -> None:
        await self.session.execute(
            delete(ProductMediaModel).where(
                ProductMediaModel.product_id == product_id
            )
        )

    # -------------------------
    # Collections
    # -------------------------

    async def create_collection(
        self,
        collection: CollectionModel,
    ) -> CollectionModel:
        self.session.add(collection)
        await self.session.flush()
        return collection

    async def get_collection(
        self,
        store_id: UUID,
        collection_id: UUID,
    ) -> CollectionModel | None:
        result = await self.session.execute(
            select(CollectionModel).where(
                CollectionModel.store_id == store_id,
                CollectionModel.collection_id == collection_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_collection_by_slug(
        self,
        store_id: UUID,
        slug: str,
    ) -> CollectionModel | None:
        result = await self.session.execute(
            select(CollectionModel).where(
                CollectionModel.store_id == store_id,
                CollectionModel.slug == slug,
            )
        )
        return result.scalar_one_or_none()

    async def list_collections(
        self,
        store_id: UUID,
        status: str | None = None,
    ) -> list[CollectionModel]:
        query = select(CollectionModel).where(
            CollectionModel.store_id == store_id
        )

        if status:
            query = query.where(CollectionModel.status == status)

        query = query.order_by(CollectionModel.created_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_collection(
        self,
        store_id: UUID,
        collection_id: UUID,
        values: dict,
    ) -> CollectionModel | None:
        await self.session.execute(
            update(CollectionModel)
            .where(
                CollectionModel.store_id == store_id,
                CollectionModel.collection_id == collection_id,
            )
            .values(**values)
        )

        return await self.get_collection(store_id, collection_id)

    # -------------------------
    # Collection Products
    # -------------------------

    async def add_collection_product(
        self,
        item: CollectionProductModel,
    ) -> CollectionProductModel:
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_collection_products(
        self,
        collection_id: UUID,
    ) -> list[CollectionProductModel]:
        result = await self.session.execute(
            select(CollectionProductModel)
            .where(CollectionProductModel.collection_id == collection_id)
            .order_by(CollectionProductModel.position)
        )
        return list(result.scalars().all())

    async def delete_collection_products(
        self,
        collection_id: UUID,
    ) -> None:
        await self.session.execute(
            delete(CollectionProductModel).where(
                CollectionProductModel.collection_id == collection_id
            )
        )

    # -------------------------
    # Tags
    # -------------------------

    async def get_tag(
        self,
        store_id: UUID,
        name: str,
    ) -> TagModel | None:
        result = await self.session.execute(
            select(TagModel).where(
                TagModel.store_id == store_id,
                TagModel.name == name,
            )
        )
        return result.scalar_one_or_none()

    async def create_tag(
        self,
        tag: TagModel,
    ) -> TagModel:
        self.session.add(tag)
        await self.session.flush()
        return tag

    async def get_product_tags(
        self,
        product_id: UUID,
    ) -> list[ProductTagModel]:
        result = await self.session.execute(
            select(ProductTagModel).where(
                ProductTagModel.product_id == product_id
            )
        )
        return list(result.scalars().all())

    async def delete_product_tags(
        self,
        product_id: UUID,
    ) -> None:
        await self.session.execute(
            delete(ProductTagModel).where(
                ProductTagModel.product_id == product_id
            )
        )

    async def add_product_tag(
        self,
        item: ProductTagModel,
    ) -> ProductTagModel:
        self.session.add(item)
        await self.session.flush()
        return item

    # -------------------------
    # Metafield Definitions
    # -------------------------

    async def create_metafield_definition(
        self,
        definition: MetafieldDefinitionModel,
    ) -> MetafieldDefinitionModel:
        self.session.add(definition)
        await self.session.flush()
        return definition

    async def get_metafield_definition(
        self,
        store_id: UUID,
        definition_id: UUID,
    ) -> MetafieldDefinitionModel | None:
        result = await self.session.execute(
            select(MetafieldDefinitionModel).where(
                MetafieldDefinitionModel.store_id == store_id,
                MetafieldDefinitionModel.definition_id == definition_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_metafield_definitions(
        self,
        store_id: UUID,
        resource_type: str | None = None,
    ) -> list[MetafieldDefinitionModel]:
        query = select(MetafieldDefinitionModel).where(
            MetafieldDefinitionModel.store_id == store_id
        )

        if resource_type:
            query = query.where(
                MetafieldDefinitionModel.resource_type == resource_type
            )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    # -------------------------
    # Metafields
    # -------------------------

    async def create_metafield(
        self,
        metafield: MetafieldModel,
    ) -> MetafieldModel:
        self.session.add(metafield)
        await self.session.flush()
        return metafield

    async def get_metafield(
        self,
        definition_id: UUID,
        resource_id: UUID,
    ) -> MetafieldModel | None:
        result = await self.session.execute(
            select(MetafieldModel).where(
                MetafieldModel.definition_id == definition_id,
                MetafieldModel.resource_id == resource_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_metafield(
        self,
        definition_id: UUID,
        resource_id: UUID,
        values: dict,
    ) -> MetafieldModel | None:
        await self.session.execute(
            update(MetafieldModel)
            .where(
                MetafieldModel.definition_id == definition_id,
                MetafieldModel.resource_id == resource_id,
            )
            .values(**values)
        )

        return await self.get_metafield(definition_id, resource_id)