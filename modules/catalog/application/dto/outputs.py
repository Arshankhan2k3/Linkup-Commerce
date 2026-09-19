from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


@dataclass
class ProductDTO:
    product_id: UUID
    store_id: UUID
    title: str
    slug: str
    description_html: str | None = None
    vendor: str | None = None
    product_type: str | None = None
    status: str = "DRAFT"
    requires_shipping: bool = True
    taxable: bool = True
    version: int = 1
    published_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class OptionValueDTO:
    option_value_id: UUID
    option_id: UUID
    value: str
    position: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OptionDTO:
    option_id: UUID
    product_id: UUID
    name: str
    position: int
    values: list[OptionValueDTO] = field(default_factory=list)


@dataclass
class VariantDTO:
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
    weight: float | None = None
    weight_unit: str | None = None
    length: float | None = None
    width: float | None = None
    height: float | None = None
    dimension_unit: str | None = None
    position: int = 0
    inventory_policy: str = "DENY"
    is_active: bool = True
    version: int = 1
    option_value_ids: list[UUID] = field(default_factory=list)


@dataclass
class MediaUploadSessionDTO:
    media_id: UUID
    upload_url: str
    headers: dict[str, str]
    expires_at: datetime


@dataclass
class MediaAssetDTO:
    media_id: UUID
    store_id: UUID
    media_type: str
    storage_key: str
    public_url: str
    alt_text: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    size_bytes: int | None = None
    created_at: datetime | None = None


@dataclass
class ProductMediaDTO:
    product_media_id: UUID
    product_id: UUID
    media_id: UUID
    variant_id: UUID | None = None
    position: int = 0
    is_primary: bool = False
    public_url: str | None = None


@dataclass
class CollectionDTO:
    collection_id: UUID
    store_id: UUID
    title: str
    slug: str
    description_html: str | None = None
    collection_type: str = "MANUAL"
    rule_json: dict[str, Any] | None = None
    status: str = "ACTIVE"
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class TagDTO:
    tag_id: UUID
    store_id: UUID
    name: str


@dataclass
class MetafieldDefinitionDTO:
    definition_id: UUID
    store_id: UUID
    resource_type: str
    namespace: str
    key: str
    value_type: str
    validation: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass
class MetafieldDTO:
    metafield_id: UUID
    definition_id: UUID
    resource_type: str
    resource_id: UUID
    value_json: Any
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class SuggestionDTO:
    text: str
    suggestion_type: str
    handle: str
    id: UUID
