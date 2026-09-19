from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
from modules.catalog.domain.enums import CollectionStatus, ProductStatus
from .models import (
    CollectionModel,
    CollectionProductModel,
    MediaAssetModel,
    MetafieldDefinitionModel,
    ProductMediaModel,
    ProductModel,
    ProductOptionModel,
    ProductOptionValueModel,
    ProductTagModel,
    ProductVariantModel,
    TagModel,
    VariantOptionValueModel,
)

T = TypeVar("T")


@dataclass
class PageInfo:
    has_next_page: bool
    has_previous_page: bool
    start_cursor: str | None = None
    end_cursor: str | None = None


@dataclass
class Edge(Generic[T]):
    node: T
    cursor: str


@dataclass
class PaginatedResult(Generic[T]):
    edges: list[Edge[T]]
    page_info: PageInfo
    total_count: int = 0


def encode_cursor(val: str) -> str:
    return base64.b64encode(val.encode("utf-8")).decode("utf-8")


def decode_cursor(cursor: str) -> str:
    return base64.b64decode(cursor.encode("utf-8")).decode("utf-8")


class CatalogQueryService:
    """Read-optimized query service for storefront and admin endpoints."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_storefront_products(
        self,
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
        first = min(max(first, 1), 100)

        stmt = select(ProductModel).where(
            ProductModel.store_id == store_id,
            ProductModel.status == ProductStatus.ACTIVE.value,
        )

        if query and query.strip():
            q_term = f"%{query.strip()}%"
            stmt = stmt.where(
                (ProductModel.title.ilike(q_term))
                | (ProductModel.description_html.ilike(q_term))
                | (ProductModel.vendor.ilike(q_term))
            )

        if collection_slug:
            stmt = (
                stmt.join(CollectionProductModel, ProductModel.product_id == CollectionProductModel.product_id)
                .join(CollectionModel, CollectionProductModel.collection_id == CollectionModel.collection_id)
                .where(CollectionModel.slug == collection_slug)
            )

        if tag_name:
            stmt = (
                stmt.join(ProductTagModel, ProductModel.product_id == ProductTagModel.product_id)
                .join(TagModel, ProductTagModel.tag_id == TagModel.tag_id)
                .where(TagModel.name.ilike(tag_name.strip()))
            )

        if min_price is not None or max_price is not None:
            var_sub = select(ProductVariantModel.product_id).where(
                ProductVariantModel.store_id == store_id,
                ProductVariantModel.is_active.is_(True),
            )
            if min_price is not None:
                var_sub = var_sub.where(ProductVariantModel.base_price >= min_price)
            if max_price is not None:
                var_sub = var_sub.where(ProductVariantModel.base_price <= max_price)
            stmt = stmt.where(ProductModel.product_id.in_(var_sub))

        # Default ordering by created_at desc
        stmt = stmt.order_by(ProductModel.created_at.desc(), ProductModel.product_id.desc())

        res = await self.session.execute(stmt)
        all_models = list(res.scalars().all())

        start_idx = 0
        if after:
            try:
                target_id = decode_cursor(after)
                for idx, m in enumerate(all_models):
                    if str(m.product_id) == target_id:
                        start_idx = idx + 1
                        break
            except Exception:
                start_idx = 0

        slice_items = all_models[start_idx : start_idx + first + 1]
        has_next = len(slice_items) > first
        nodes = slice_items[:first]

        edges: list[Edge[ProductDTO]] = []
        for m in nodes:
            dto = ProductDTO(
                product_id=m.product_id,
                store_id=m.store_id,
                title=m.title,
                slug=m.slug,
                description_html=m.description_html,
                vendor=m.vendor,
                product_type=m.product_type,
                status=m.status,
                requires_shipping=m.requires_shipping,
                taxable=m.taxable,
                version=m.version,
                published_at=m.published_at,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            cursor = encode_cursor(str(m.product_id))
            edges.append(Edge(node=dto, cursor=cursor))

        page_info = PageInfo(
            has_next_page=has_next,
            has_previous_page=start_idx > 0,
            start_cursor=edges[0].cursor if edges else None,
            end_cursor=edges[-1].cursor if edges else None,
        )

        return PaginatedResult(edges=edges, page_info=page_info, total_count=len(all_models))

    async def get_storefront_product_detail(self, store_id: UUID, handle: str) -> dict | None:
        stmt = select(ProductModel).where(
            ProductModel.store_id == store_id,
            ProductModel.slug == handle,
            ProductModel.status == ProductStatus.ACTIVE.value,
        )
        res = await self.session.execute(stmt)
        product = res.scalar_one_or_none()
        if not product:
            return None

        # Fetch active variants
        v_res = await self.session.execute(
            select(ProductVariantModel)
            .where(
                ProductVariantModel.product_id == product.product_id,
                ProductVariantModel.is_active.is_(True),
            )
            .order_by(ProductVariantModel.position)
        )
        variants = list(v_res.scalars().all())

        # Options & option values
        o_res = await self.session.execute(
            select(ProductOptionModel)
            .where(ProductOptionModel.product_id == product.product_id)
            .order_by(ProductOptionModel.position)
        )
        options = list(o_res.scalars().all())

        opt_dtos = []
        for opt in options:
            ov_res = await self.session.execute(
                select(ProductOptionValueModel)
                .where(ProductOptionValueModel.option_id == opt.option_id)
                .order_by(ProductOptionValueModel.position)
            )
            ovs = list(ov_res.scalars().all())
            opt_dtos.append(
                OptionDTO(
                    option_id=opt.option_id,
                    product_id=opt.product_id,
                    name=opt.name,
                    position=opt.position,
                    values=[
                        OptionValueDTO(
                            option_value_id=v.option_value_id,
                            option_id=v.option_id,
                            value=v.value,
                            position=v.position,
                            metadata=v.metadata_json,
                        )
                        for v in ovs
                    ],
                )
            )

        # Media assets
        pm_res = await self.session.execute(
            select(ProductMediaModel, MediaAssetModel)
            .join(MediaAssetModel, ProductMediaModel.media_id == MediaAssetModel.media_id)
            .where(ProductMediaModel.product_id == product.product_id)
            .order_by(ProductMediaModel.position)
        )
        media_items = pm_res.all()
        media_dtos = [
            ProductMediaDTO(
                product_media_id=pm.product_media_id,
                product_id=pm.product_id,
                media_id=pm.media_id,
                variant_id=pm.variant_id,
                position=pm.position,
                is_primary=pm.is_primary,
                public_url=ma.public_url,
            )
            for pm, ma in media_items
        ]

        var_dtos = []
        for v in variants:
            ov_sub = await self.session.execute(
                select(VariantOptionValueModel.option_value_id).where(
                    VariantOptionValueModel.variant_id == v.variant_id
                )
            )
            ov_ids = list(ov_sub.scalars().all())
            var_dtos.append(
                VariantDTO(
                    variant_id=v.variant_id,
                    store_id=v.store_id,
                    product_id=v.product_id,
                    option_signature=v.option_signature,
                    base_price=v.base_price,
                    currency=v.currency,
                    sku=v.sku,
                    barcode=v.barcode,
                    title=v.title,
                    compare_at_price=v.compare_at_price,
                    weight=float(v.weight) if v.weight else None,
                    weight_unit=v.weight_unit,
                    position=v.position,
                    is_active=v.is_active,
                    option_value_ids=ov_ids,
                )
            )

        prod_dto = ProductDTO(
            product_id=product.product_id,
            store_id=product.store_id,
            title=product.title,
            slug=product.slug,
            description_html=product.description_html,
            vendor=product.vendor,
            product_type=product.product_type,
            status=product.status,
            requires_shipping=product.requires_shipping,
            taxable=product.taxable,
            published_at=product.published_at,
            created_at=product.created_at,
            updated_at=product.updated_at,
        )

        return {
            "product": prod_dto,
            "options": opt_dtos,
            "variants": var_dtos,
            "media": media_dtos,
        }

    async def list_storefront_collections(
        self,
        store_id: UUID,
        first: int = 20,
        after: str | None = None,
    ) -> PaginatedResult[CollectionDTO]:
        first = min(max(first, 1), 100)
        stmt = (
            select(CollectionModel)
            .where(
                CollectionModel.store_id == store_id,
                CollectionModel.status == CollectionStatus.ACTIVE.value,
            )
            .order_by(CollectionModel.created_at.desc())
        )
        res = await self.session.execute(stmt)
        all_models = list(res.scalars().all())

        start_idx = 0
        if after:
            try:
                target_id = decode_cursor(after)
                for idx, m in enumerate(all_models):
                    if str(m.collection_id) == target_id:
                        start_idx = idx + 1
                        break
            except Exception:
                start_idx = 0

        slice_items = all_models[start_idx : start_idx + first + 1]
        has_next = len(slice_items) > first
        nodes = slice_items[:first]

        edges: list[Edge[CollectionDTO]] = []
        for m in nodes:
            dto = CollectionDTO(
                collection_id=m.collection_id,
                store_id=m.store_id,
                title=m.title,
                slug=m.slug,
                description_html=m.description_html,
                collection_type=m.collection_type,
                rule_json=m.rule_json,
                status=m.status,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            cursor = encode_cursor(str(m.collection_id))
            edges.append(Edge(node=dto, cursor=cursor))

        return PaginatedResult(
            edges=edges,
            page_info=PageInfo(
                has_next_page=has_next,
                has_previous_page=start_idx > 0,
                start_cursor=edges[0].cursor if edges else None,
                end_cursor=edges[-1].cursor if edges else None,
            ),
            total_count=len(all_models),
        )

    async def get_storefront_collection_detail(
        self,
        store_id: UUID,
        handle: str,
        first: int = 20,
        after: str | None = None,
        sort: str | None = None,
    ) -> dict | None:
        stmt = select(CollectionModel).where(
            CollectionModel.store_id == store_id,
            CollectionModel.slug == handle,
            CollectionModel.status == CollectionStatus.ACTIVE.value,
        )
        res = await self.session.execute(stmt)
        collection = res.scalar_one_or_none()
        if not collection:
            return None

        coll_dto = CollectionDTO(
            collection_id=collection.collection_id,
            store_id=collection.store_id,
            title=collection.title,
            slug=collection.slug,
            description_html=collection.description_html,
            collection_type=collection.collection_type,
            rule_json=collection.rule_json,
            status=collection.status,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        )

        products_connection = await self.list_storefront_products(
            store_id=store_id,
            first=first,
            after=after,
            collection_slug=handle,
            sort=sort,
        )

        return {
            "collection": coll_dto,
            "products": products_connection,
        }

    async def get_suggestions(
        self,
        store_id: UUID,
        query: str,
        limit: int = 10,
    ) -> list[SuggestionDTO]:
        q_term = f"%{query.strip()}%"
        p_stmt = (
            select(ProductModel)
            .where(
                ProductModel.store_id == store_id,
                ProductModel.status == ProductStatus.ACTIVE.value,
                ProductModel.title.ilike(q_term),
            )
            .limit(limit)
        )
        p_res = await self.session.execute(p_stmt)
        products = list(p_res.scalars().all())

        c_stmt = (
            select(CollectionModel)
            .where(
                CollectionModel.store_id == store_id,
                CollectionModel.status == CollectionStatus.ACTIVE.value,
                CollectionModel.title.ilike(q_term),
            )
            .limit(limit)
        )
        c_res = await self.session.execute(c_stmt)
        collections = list(c_res.scalars().all())

        results: list[SuggestionDTO] = []
        for p in products[:limit]:
            results.append(
                SuggestionDTO(
                    text=p.title,
                    suggestion_type="PRODUCT",
                    handle=p.slug,
                    id=p.product_id,
                )
            )

        for c in collections[: limit - len(results)]:
            results.append(
                SuggestionDTO(
                    text=c.title,
                    suggestion_type="COLLECTION",
                    handle=c.slug,
                    id=c.collection_id,
                )
            )

        return results

    async def list_admin_products(
        self,
        store_id: UUID,
        first: int = 20,
        after: str | None = None,
        query: str | None = None,
        status: str | None = None,
        vendor: str | None = None,
        tag: str | None = None,
    ) -> PaginatedResult[ProductDTO]:
        first = min(max(first, 1), 100)
        stmt = select(ProductModel).where(ProductModel.store_id == store_id)

        if status:
            stmt = stmt.where(ProductModel.status == status.upper())
        if vendor:
            stmt = stmt.where(ProductModel.vendor.ilike(f"%{vendor.strip()}%"))
        if query:
            q_term = f"%{query.strip()}%"
            stmt = stmt.where(
                (ProductModel.title.ilike(q_term)) | (ProductModel.slug.ilike(q_term))
            )

        if tag:
            stmt = (
                stmt.join(ProductTagModel, ProductModel.product_id == ProductTagModel.product_id)
                .join(TagModel, ProductTagModel.tag_id == TagModel.tag_id)
                .where(TagModel.name.ilike(tag.strip()))
            )

        stmt = stmt.order_by(ProductModel.created_at.desc())
        res = await self.session.execute(stmt)
        all_models = list(res.scalars().all())

        start_idx = 0
        if after:
            try:
                target_id = decode_cursor(after)
                for idx, m in enumerate(all_models):
                    if str(m.product_id) == target_id:
                        start_idx = idx + 1
                        break
            except Exception:
                start_idx = 0

        slice_items = all_models[start_idx : start_idx + first + 1]
        has_next = len(slice_items) > first
        nodes = slice_items[:first]

        edges: list[Edge[ProductDTO]] = []
        for m in nodes:
            dto = ProductDTO(
                product_id=m.product_id,
                store_id=m.store_id,
                title=m.title,
                slug=m.slug,
                description_html=m.description_html,
                vendor=m.vendor,
                product_type=m.product_type,
                status=m.status,
                requires_shipping=m.requires_shipping,
                taxable=m.taxable,
                version=m.version,
                published_at=m.published_at,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            cursor = encode_cursor(str(m.product_id))
            edges.append(Edge(node=dto, cursor=cursor))

        return PaginatedResult(
            edges=edges,
            page_info=PageInfo(
                has_next_page=has_next,
                has_previous_page=start_idx > 0,
                start_cursor=edges[0].cursor if edges else None,
                end_cursor=edges[-1].cursor if edges else None,
            ),
            total_count=len(all_models),
        )

    async def get_admin_product_detail(self, store_id: UUID, product_id: UUID) -> dict | None:
        stmt = select(ProductModel).where(
            ProductModel.store_id == store_id,
            ProductModel.product_id == product_id,
        )
        res = await self.session.execute(stmt)
        product = res.scalar_one_or_none()
        if not product:
            return None

        # Fetch variants
        v_res = await self.session.execute(
            select(ProductVariantModel)
            .where(ProductVariantModel.product_id == product_id)
            .order_by(ProductVariantModel.position)
        )
        variants = list(v_res.scalars().all())

        # Fetch options
        o_res = await self.session.execute(
            select(ProductOptionModel)
            .where(ProductOptionModel.product_id == product_id)
            .order_by(ProductOptionModel.position)
        )
        options = list(o_res.scalars().all())

        opt_dtos = []
        for opt in options:
            ov_res = await self.session.execute(
                select(ProductOptionValueModel)
                .where(ProductOptionValueModel.option_id == opt.option_id)
                .order_by(ProductOptionValueModel.position)
            )
            ovs = list(ov_res.scalars().all())
            opt_dtos.append(
                OptionDTO(
                    option_id=opt.option_id,
                    product_id=opt.product_id,
                    name=opt.name,
                    position=opt.position,
                    values=[
                        OptionValueDTO(
                            option_value_id=v.option_value_id,
                            option_id=v.option_id,
                            value=v.value,
                            position=v.position,
                            metadata=v.metadata_json,
                        )
                        for v in ovs
                    ],
                )
            )

        # Fetch tags
        t_res = await self.session.execute(
            select(TagModel)
            .join(ProductTagModel, TagModel.tag_id == ProductTagModel.tag_id)
            .where(ProductTagModel.product_id == product_id)
        )
        tags = list(t_res.scalars().all())
        tag_dtos = [TagDTO(tag_id=t.tag_id, store_id=t.store_id, name=t.name) for t in tags]

        # Fetch media
        pm_res = await self.session.execute(
            select(ProductMediaModel, MediaAssetModel)
            .join(MediaAssetModel, ProductMediaModel.media_id == MediaAssetModel.media_id)
            .where(ProductMediaModel.product_id == product_id)
            .order_by(ProductMediaModel.position)
        )
        media_items = pm_res.all()
        media_dtos = [
            ProductMediaDTO(
                product_media_id=pm.product_media_id,
                product_id=pm.product_id,
                media_id=pm.media_id,
                variant_id=pm.variant_id,
                position=pm.position,
                is_primary=pm.is_primary,
                public_url=ma.public_url,
            )
            for pm, ma in media_items
        ]

        var_dtos = []
        for v in variants:
            ov_sub = await self.session.execute(
                select(VariantOptionValueModel.option_value_id).where(
                    VariantOptionValueModel.variant_id == v.variant_id
                )
            )
            ov_ids = list(ov_sub.scalars().all())
            var_dtos.append(
                VariantDTO(
                    variant_id=v.variant_id,
                    store_id=v.store_id,
                    product_id=v.product_id,
                    option_signature=v.option_signature,
                    base_price=v.base_price,
                    currency=v.currency,
                    sku=v.sku,
                    barcode=v.barcode,
                    title=v.title,
                    compare_at_price=v.compare_at_price,
                    cost_price=v.cost_price,
                    weight=float(v.weight) if v.weight else None,
                    weight_unit=v.weight_unit,
                    position=v.position,
                    is_active=v.is_active,
                    version=v.version,
                    option_value_ids=ov_ids,
                )
            )

        prod_dto = ProductDTO(
            product_id=product.product_id,
            store_id=product.store_id,
            title=product.title,
            slug=product.slug,
            description_html=product.description_html,
            vendor=product.vendor,
            product_type=product.product_type,
            status=product.status,
            requires_shipping=product.requires_shipping,
            taxable=product.taxable,
            version=product.version,
            published_at=product.published_at,
            created_at=product.created_at,
            updated_at=product.updated_at,
        )

        return {
            "product": prod_dto,
            "options": opt_dtos,
            "variants": var_dtos,
            "tags": tag_dtos,
            "media": media_dtos,
        }

    async def list_admin_collections(
        self,
        store_id: UUID,
        first: int = 20,
        after: str | None = None,
        query: str | None = None,
        status: str | None = None,
    ) -> PaginatedResult[CollectionDTO]:
        first = min(max(first, 1), 100)
        stmt = select(CollectionModel).where(CollectionModel.store_id == store_id)

        if status:
            stmt = stmt.where(CollectionModel.status == status.upper())
        if query:
            stmt = stmt.where(CollectionModel.title.ilike(f"%{query.strip()}%"))

        stmt = stmt.order_by(CollectionModel.created_at.desc())
        res = await self.session.execute(stmt)
        all_models = list(res.scalars().all())

        start_idx = 0
        if after:
            try:
                target_id = decode_cursor(after)
                for idx, m in enumerate(all_models):
                    if str(m.collection_id) == target_id:
                        start_idx = idx + 1
                        break
            except Exception:
                start_idx = 0

        slice_items = all_models[start_idx : start_idx + first + 1]
        has_next = len(slice_items) > first
        nodes = slice_items[:first]

        edges: list[Edge[CollectionDTO]] = []
        for m in nodes:
            dto = CollectionDTO(
                collection_id=m.collection_id,
                store_id=m.store_id,
                title=m.title,
                slug=m.slug,
                description_html=m.description_html,
                collection_type=m.collection_type,
                rule_json=m.rule_json,
                status=m.status,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            cursor = encode_cursor(str(m.collection_id))
            edges.append(Edge(node=dto, cursor=cursor))

        return PaginatedResult(
            edges=edges,
            page_info=PageInfo(
                has_next_page=has_next,
                has_previous_page=start_idx > 0,
                start_cursor=edges[0].cursor if edges else None,
                end_cursor=edges[-1].cursor if edges else None,
            ),
            total_count=len(all_models),
        )

    async def list_metafield_definitions(
        self,
        store_id: UUID,
        resource_type: str | None = None,
    ) -> list[MetafieldDefinitionDTO]:
        stmt = select(MetafieldDefinitionModel).where(MetafieldDefinitionModel.store_id == store_id)
        if resource_type:
            stmt = stmt.where(MetafieldDefinitionModel.resource_type == resource_type.upper())

        res = await self.session.execute(stmt)
        models = list(res.scalars().all())
        return [
            MetafieldDefinitionDTO(
                definition_id=m.definition_id,
                store_id=m.store_id,
                resource_type=m.resource_type,
                namespace=m.namespace,
                key=m.key,
                value_type=m.value_type,
                validation=m.validation,
                created_at=m.created_at,
            )
            for m in models
        ]
