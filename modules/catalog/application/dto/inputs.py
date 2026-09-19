from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


@dataclass
class CreateProductInput:
    store_id: UUID
    title: str
    slug: str | None = None
    description_html: str | None = None
    vendor: str | None = None
    product_type: str | None = None
    status: str = "DRAFT"
    requires_shipping: bool = True
    taxable: bool = True
    tags: list[str] = field(default_factory=list)


@dataclass
class UpdateProductInput:
    store_id: UUID
    product_id: UUID
    title: str | None = None
    slug: str | None = None
    description_html: str | None = None
    vendor: str | None = None
    product_type: str | None = None
    status: str | None = None
    requires_shipping: bool | None = None
    taxable: bool | None = None
    version: int | None = None


@dataclass
class CreateOptionInput:
    product_id: UUID
    name: str
    position: int = 0
    values: list[CreateOptionValueInput] = field(default_factory=list)


@dataclass
class CreateOptionValueInput:
    value: str
    position: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class UpdateOptionInput:
    product_id: UUID
    option_id: UUID
    name: str | None = None
    position: int | None = None
    values: list[CreateOptionValueInput] | None = None


@dataclass
class CreateVariantInput:
    store_id: UUID
    product_id: UUID
    base_price: Decimal
    sku: str | None = None
    barcode: str | None = None
    option_value_ids: list[UUID] = field(default_factory=list)
    title: str | None = None
    compare_at_price: Decimal | None = None
    cost_price: Decimal | None = None
    currency: str = "USD"
    weight: Decimal | float | None = None
    weight_unit: str | None = None
    length: Decimal | float | None = None
    width: Decimal | float | None = None
    height: Decimal | float | None = None
    dimension_unit: str | None = None
    is_active: bool = True


@dataclass
class UpdateVariantInput:
    store_id: UUID
    variant_id: UUID
    sku: str | None = None
    barcode: str | None = None
    base_price: Decimal | None = None
    compare_at_price: Decimal | None = None
    cost_price: Decimal | None = None
    weight: Decimal | float | None = None
    weight_unit: str | None = None
    length: Decimal | float | None = None
    width: Decimal | float | None = None
    height: Decimal | float | None = None
    dimension_unit: str | None = None
    is_active: bool | None = None
    version: int | None = None


@dataclass
class BulkVariantItemInput:
    variant_id: UUID | None = None
    sku: str | None = None
    barcode: str | None = None
    base_price: Decimal = Decimal("0.00")
    option_value_ids: list[UUID] = field(default_factory=list)
    compare_at_price: Decimal | None = None
    is_active: bool = True


@dataclass
class CreateMediaSessionInput:
    store_id: UUID
    filename: str
    content_type: str
    size_bytes: int
    checksum: str | None = None


@dataclass
class CompleteMediaInput:
    store_id: UUID
    media_id: UUID
    checksum: str | None = None
    width: int | None = None
    height: int | None = None


@dataclass
class ProductMediaItemInput:
    media_id: UUID
    position: int = 0
    is_primary: bool = False
    variant_id: UUID | None = None


@dataclass
class CreateCollectionInput:
    store_id: UUID
    title: str
    slug: str | None = None
    description_html: str | None = None
    collection_type: str = "MANUAL"
    rule_json: dict[str, Any] | None = None
    status: str = "ACTIVE"


@dataclass
class UpdateCollectionInput:
    store_id: UUID
    collection_id: UUID
    title: str | None = None
    slug: str | None = None
    description_html: str | None = None
    status: str | None = None
    rule_json: dict[str, Any] | None = None


@dataclass
class CreateMetafieldDefinitionInput:
    store_id: UUID
    resource_type: str
    namespace: str
    key: str
    value_type: str
    validation: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetafieldItemInput:
    definition_id: UUID
    value: Any
