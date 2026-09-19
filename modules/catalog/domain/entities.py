from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from .enums import (
    CollectionStatus,
    CollectionType,
    InventoryPolicy,
    MediaType,
    MetafieldOwnerType,
    MetafieldValueType,
    ProductStatus,
)


@dataclass
class Product:
    product_id: UUID
    store_id: UUID
    title: str
    slug: str
    description_html: str | None = None
    vendor: str | None = None
    product_type: str | None = None
    status: ProductStatus = ProductStatus.DRAFT
    requires_shipping: bool = True
    taxable: bool = True
    version: int = 1
    published_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class ProductOption:
    option_id: UUID
    product_id: UUID
    name: str
    position: int
    created_at: datetime | None = None


@dataclass
class ProductOptionValue:
    option_value_id: UUID
    option_id: UUID
    value: str
    position: int
    metadata_json: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass
class ProductVariant:
    variant_id: UUID
    store_id: UUID
    product_id: UUID
    option_signature: str
    base_price: Decimal
    currency: str = "USD"
    sku: str | None = None
    barcode: str | None = None
    title: str | None = None
    compare_at_price: Decimal | None = None
    cost_price: Decimal | None = None
    weight: Decimal | float | None = None
    weight_unit: str | None = None
    length: Decimal | float | None = None
    width: Decimal | float | None = None
    height: Decimal | float | None = None
    dimension_unit: str | None = None
    position: int = 0
    inventory_policy: InventoryPolicy = InventoryPolicy.DENY
    is_active: bool = True
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class VariantOptionValue:
    variant_id: UUID
    option_value_id: UUID
    created_at: datetime | None = None


@dataclass
class MediaAsset:
    media_id: UUID
    store_id: UUID
    media_type: MediaType
    storage_key: str
    public_url: str
    alt_text: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    size_bytes: int | None = None
    created_at: datetime | None = None


@dataclass
class ProductMedia:
    product_media_id: UUID
    product_id: UUID
    media_id: UUID
    variant_id: UUID | None = None
    position: int = 0
    is_primary: bool = False
    created_at: datetime | None = None


@dataclass
class Collection:
    collection_id: UUID
    store_id: UUID
    title: str
    slug: str
    description_html: str | None = None
    collection_type: CollectionType = CollectionType.MANUAL
    rule_json: dict[str, Any] | None = None
    status: CollectionStatus = CollectionStatus.ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class CollectionProduct:
    collection_id: UUID
    product_id: UUID
    position: int = 0
    created_at: datetime | None = None


@dataclass
class Tag:
    tag_id: UUID
    store_id: UUID
    name: str
    created_at: datetime | None = None


@dataclass
class ProductTag:
    product_id: UUID
    tag_id: UUID
    created_at: datetime | None = None


@dataclass
class MetafieldDefinition:
    definition_id: UUID
    store_id: UUID
    resource_type: MetafieldOwnerType
    namespace: str
    key: str
    value_type: MetafieldValueType
    validation: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass
class Metafield:
    metafield_id: UUID
    definition_id: UUID
    resource_type: MetafieldOwnerType
    resource_id: UUID
    value_json: Any
    created_at: datetime | None = None
    updated_at: datetime | None = None