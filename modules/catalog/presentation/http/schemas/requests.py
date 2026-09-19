from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ProductCreateRequest(BaseModel):
    title: str = Field(..., max_length=255)
    description: str | None = None
    vendor: str | None = None
    product_type: str | None = None
    status: str = "DRAFT"
    handle: str | None = None
    requires_shipping: bool = True
    taxable: bool = True
    tags: list[str] = Field(default_factory=list)


class ProductPatchRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    vendor: str | None = None
    product_type: str | None = None
    status: str | None = None
    handle: str | None = None
    requires_shipping: bool | None = None
    taxable: bool | None = None
    version: int | None = None


class PublishProductRequest(BaseModel):
    published_at: str | None = None


class CreateOptionValuePayload(BaseModel):
    value: str
    position: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateOptionRequest(BaseModel):
    name: str = Field(..., max_length=80)
    position: int = 0
    values: list[CreateOptionValuePayload] = Field(default_factory=list)


class PatchOptionRequest(BaseModel):
    name: str | None = None
    position: int | None = None
    values: list[CreateOptionValuePayload] | None = None


class CreateVariantRequest(BaseModel):
    sku: str | None = None
    barcode: str | None = None
    option_value_ids: list[UUID] = Field(default_factory=list)
    price: Decimal = Field(..., alias="base_price")
    compare_at_price: Decimal | None = None
    cost_price: Decimal | None = None
    weight: Decimal | None = None
    weight_unit: str | None = None
    length: Decimal | None = None
    width: Decimal | None = None
    height: Decimal | None = None
    dimension_unit: str | None = None
    status: str = "ACTIVE"
    is_active: bool = True

    class Config:
        populate_by_name = True


class BulkVariantItem(BaseModel):
    variant_id: UUID | None = None
    sku: str | None = None
    barcode: str | None = None
    price: Decimal = Field(Decimal("0.00"), alias="base_price")
    option_value_ids: list[UUID] = Field(default_factory=list)
    compare_at_price: Decimal | None = None
    is_active: bool = True

    class Config:
        populate_by_name = True


class BulkVariantRequest(BaseModel):
    items: list[BulkVariantItem] = Field(..., max_length=100)


class PatchVariantRequest(BaseModel):
    sku: str | None = None
    barcode: str | None = None
    price: Decimal | None = Field(None, alias="base_price")
    compare_at_price: Decimal | None = None
    cost_price: Decimal | None = None
    weight: Decimal | None = None
    weight_unit: str | None = None
    status: str | None = None
    is_active: bool | None = None
    version: int | None = None

    class Config:
        populate_by_name = True


class MediaUploadSessionRequest(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    checksum: str | None = None


class FinalizeMediaRequest(BaseModel):
    checksum: str | None = None
    width: int | None = None
    height: int | None = None


class ProductMediaLinkItem(BaseModel):
    media_id: UUID
    variant_id: UUID | None = None
    position: int = 0
    is_primary: bool = False


class ReplaceProductMediaRequest(BaseModel):
    media_ids: list[UUID] = Field(default_factory=list)
    featured_media_id: UUID | None = None
    items: list[ProductMediaLinkItem] = Field(default_factory=list)


class CreateCollectionRequest(BaseModel):
    title: str = Field(..., max_length=200)
    handle: str | None = None
    description: str | None = Field(None, alias="description_html")
    status: str = "ACTIVE"
    collection_type: str = "MANUAL"
    rule_json: dict[str, Any] | None = None

    class Config:
        populate_by_name = True


class CollectionPatchRequest(BaseModel):
    title: str | None = None
    handle: str | None = None
    description: str | None = Field(None, alias="description_html")
    status: str | None = None
    rule_json: dict[str, Any] | None = None

    class Config:
        populate_by_name = True


class CollectionProductsReplaceRequest(BaseModel):
    product_ids: list[UUID] = Field(default_factory=list)


class ReplaceProductTagsRequest(BaseModel):
    tags: list[str] = Field(default_factory=list)


class CreateMetafieldDefinitionRequest(BaseModel):
    namespace: str
    key: str
    owner_type: str = Field(..., alias="resource_type")
    data_type: str = Field(..., alias="value_type")
    validation: dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True


class MetafieldUpsertItem(BaseModel):
    definition_id: UUID
    value: Any


class UpsertMetafieldsRequest(BaseModel):
    values: list[MetafieldUpsertItem] = Field(default_factory=list)