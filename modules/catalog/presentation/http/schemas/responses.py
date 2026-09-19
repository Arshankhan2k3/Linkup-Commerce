from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ProductResponse(BaseModel):
    product_id: UUID
    store_id: UUID
    title: str
    slug: str
    description_html: str | None = None
    vendor: str | None = None
    product_type: str | None = None
    status: str
    requires_shipping: bool
    taxable: bool
    version: int
    published_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OptionValueResponse(BaseModel):
    option_value_id: UUID
    option_id: UUID
    value: str
    position: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductOptionResponse(BaseModel):
    option_id: UUID
    product_id: UUID
    name: str
    position: int
    values: list[OptionValueResponse] = Field(default_factory=list)


class VariantResponse(BaseModel):
    variant_id: UUID
    store_id: UUID
    product_id: UUID
    option_signature: str
    base_price: Decimal
    currency: str
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
    position: int
    inventory_policy: str
    is_active: bool
    version: int
    option_value_ids: list[UUID] = Field(default_factory=list)


class MediaUploadSessionResponse(BaseModel):
    media_id: UUID
    upload_url: str
    headers: dict[str, str]
    expires_at: datetime


class MediaAssetResponse(BaseModel):
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


class ProductMediaResponse(BaseModel):
    product_media_id: UUID
    product_id: UUID
    media_id: UUID
    variant_id: UUID | None = None
    position: int
    is_primary: bool
    public_url: str | None = None


class CollectionResponse(BaseModel):
    collection_id: UUID
    store_id: UUID
    title: str
    slug: str
    description_html: str | None = None
    collection_type: str
    rule_json: dict[str, Any] | None = None
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TagResponse(BaseModel):
    tag_id: UUID
    store_id: UUID
    name: str


class MetafieldDefinitionResponse(BaseModel):
    definition_id: UUID
    store_id: UUID
    resource_type: str
    namespace: str
    key: str
    value_type: str
    validation: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class MetafieldResponse(BaseModel):
    metafield_id: UUID
    definition_id: UUID
    resource_type: str
    resource_id: UUID
    value_json: Any
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SuggestionItemResponse(BaseModel):
    text: str
    suggestion_type: str
    handle: str
    id: UUID


class SuggestionResponse(BaseModel):
    suggestions: list[SuggestionItemResponse]


class ProductDetailResponse(BaseModel):
    product: ProductResponse
    options: list[ProductOptionResponse]
    variants: list[VariantResponse]
    media: list[ProductMediaResponse]


class AdminProductDetailResponse(BaseModel):
    product: ProductResponse
    options: list[ProductOptionResponse]
    variants: list[VariantResponse]
    tags: list[TagResponse]
    media: list[ProductMediaResponse]


class CollectionDetailResponse(BaseModel):
    collection: CollectionResponse
    products: Any


class BulkVariantResult(BaseModel):
    items: list[VariantResponse]