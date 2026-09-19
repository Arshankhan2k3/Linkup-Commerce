from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from modules.catalog.application.dto.inputs import CreateProductInput, UpdateProductInput
from modules.catalog.application.dto.outputs import ProductDTO
from modules.catalog.domain.enums import ProductStatus
from modules.catalog.domain.events import ProductCreated, ProductPublished, ProductUpdated
from modules.catalog.domain.exceptions import (
    ConcurrencyError,
    InvalidProductError,
    ProductAlreadyExistsError,
    ProductNotFoundError,
)
from modules.catalog.domain.policies import ProductPublishPolicy
from modules.catalog.domain.services import PureDomainCatalogService
from modules.catalog.infrastructure.db.models import ProductModel, ProductVariantModel
from modules.catalog.infrastructure.db.repositories import CatalogRepository


def _model_to_dto(model: ProductModel) -> ProductDTO:
    return ProductDTO(
        product_id=model.product_id,
        store_id=model.store_id,
        title=model.title,
        slug=model.slug,
        description_html=model.description_html,
        vendor=model.vendor,
        product_type=model.product_type,
        status=model.status,
        requires_shipping=model.requires_shipping,
        taxable=model.taxable,
        version=model.version,
        published_at=model.published_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


async def execute_create_product(
    repository: CatalogRepository,
    input_dto: CreateProductInput,
) -> tuple[ProductDTO, ProductCreated]:
    slug = input_dto.slug or PureDomainCatalogService.slugify(input_dto.title)

    existing = await repository.get_product_by_slug(input_dto.store_id, slug)
    if existing:
        raise ProductAlreadyExistsError(f"Product with handle '{slug}' already exists")

    product_id = uuid4()
    model = ProductModel(
        product_id=product_id,
        store_id=input_dto.store_id,
        title=input_dto.title,
        slug=slug,
        description_html=input_dto.description_html,
        vendor=input_dto.vendor,
        product_type=input_dto.product_type,
        status=input_dto.status or ProductStatus.DRAFT.value,
        requires_shipping=input_dto.requires_shipping,
        taxable=input_dto.taxable,
    )

    created = await repository.create_product(model)
    event = ProductCreated(
        product_id=created.product_id,
        store_id=created.store_id,
        title=created.title,
        slug=created.slug,
    )
    return _model_to_dto(created), event


async def execute_update_product(
    repository: CatalogRepository,
    input_dto: UpdateProductInput,
) -> tuple[ProductDTO, ProductUpdated]:
    product = await repository.get_product(input_dto.store_id, input_dto.product_id)
    if not product:
        raise ProductNotFoundError(f"Product '{input_dto.product_id}' not found")

    if input_dto.version is not None and product.version != input_dto.version:
        raise ConcurrencyError("Product has been modified by another transaction")

    values: dict = {}
    if input_dto.title is not None:
        values["title"] = input_dto.title
    if input_dto.slug is not None:
        slug = PureDomainCatalogService.slugify(input_dto.slug)
        existing = await repository.get_product_by_slug(input_dto.store_id, slug)
        if existing and existing.product_id != input_dto.product_id:
            raise ProductAlreadyExistsError(f"Product with handle '{slug}' already exists")
        values["slug"] = slug
    if input_dto.description_html is not None:
        values["description_html"] = input_dto.description_html
    if input_dto.vendor is not None:
        values["vendor"] = input_dto.vendor
    if input_dto.product_type is not None:
        values["product_type"] = input_dto.product_type
    if input_dto.status is not None:
        values["status"] = input_dto.status
    if input_dto.requires_shipping is not None:
        values["requires_shipping"] = input_dto.requires_shipping
    if input_dto.taxable is not None:
        values["taxable"] = input_dto.taxable

    values["version"] = product.version + 1
    values["updated_at"] = datetime.now(timezone.utc)

    updated = await repository.update_product(input_dto.store_id, input_dto.product_id, values)
    if not updated:
        raise ProductNotFoundError(f"Product '{input_dto.product_id}' not found")

    event = ProductUpdated(product_id=updated.product_id, store_id=updated.store_id)
    return _model_to_dto(updated), event


async def execute_publish_product(
    repository: CatalogRepository,
    store_id: UUID,
    product_id: UUID,
    published_at_str: str | None = None,
) -> tuple[ProductDTO, ProductPublished]:
    product = await repository.get_product(store_id, product_id)
    if not product:
        raise ProductNotFoundError(f"Product '{product_id}' not found")

    variants = await repository.list_variants(product_id)

    # Validate using domain policy
    from modules.catalog.domain.entities import Product as DomainProduct, ProductVariant as DomainVariant
    domain_prod = DomainProduct(
        product_id=product.product_id,
        store_id=product.store_id,
        title=product.title,
        slug=product.slug,
        status=product.status,
    )
    domain_vars = [
        DomainVariant(
            variant_id=v.variant_id,
            store_id=v.store_id,
            product_id=v.product_id,
            option_signature=v.option_signature,
            base_price=v.base_price,
            currency=v.currency,
            is_active=v.is_active,
        )
        for v in variants
    ]

    ProductPublishPolicy.validate_for_publishing(domain_prod, domain_vars)

    now = datetime.now(timezone.utc)
    pub_time = now
    if published_at_str:
        try:
            pub_time = datetime.fromisoformat(published_at_str)
        except ValueError:
            pub_time = now

    values = {
        "status": ProductStatus.ACTIVE.value,
        "published_at": product.published_at or pub_time,
        "version": product.version + 1,
        "updated_at": now,
    }

    updated = await repository.update_product(store_id, product_id, values)
    if not updated:
        raise ProductNotFoundError(f"Product '{product_id}' not found")

    event = ProductPublished(product_id=product_id, store_id=store_id, published_at=updated.published_at or now)
    return _model_to_dto(updated), event


async def execute_archive_product(
    repository: CatalogRepository,
    store_id: UUID,
    product_id: UUID,
) -> tuple[ProductDTO, ProductUpdated]:
    product = await repository.get_product(store_id, product_id)
    if not product:
        raise ProductNotFoundError(f"Product '{product_id}' not found")

    values = {
        "status": ProductStatus.ARCHIVED.value,
        "version": product.version + 1,
        "updated_at": datetime.now(timezone.utc),
    }

    updated = await repository.update_product(store_id, product_id, values)
    if not updated:
        raise ProductNotFoundError(f"Product '{product_id}' not found")

    event = ProductUpdated(product_id=product_id, store_id=store_id)
    return _model_to_dto(updated), event


async def execute_delete_product(
    repository: CatalogRepository,
    store_id: UUID,
    product_id: UUID,
) -> None:
    product = await repository.get_product(store_id, product_id)
    if not product:
        raise ProductNotFoundError(f"Product '{product_id}' not found")

    if product.status != ProductStatus.DRAFT.value:
        raise InvalidProductError("Only DRAFT products can be deleted. Published or archived products must be archived.")

    deleted = await repository.delete_product(store_id, product_id)
    if not deleted:
        raise ProductNotFoundError(f"Product '{product_id}' not found")
