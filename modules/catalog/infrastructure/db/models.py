from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import (
    BigInteger,
    Boolean,
    CHAR,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from decimal import Decimal
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# 1. PRODUCTS
# ============================================================

class ProductModel(Base):
    __tablename__ = "products"

    product_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
    )

    store_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("stores.store_id"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description_html: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    vendor: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
        index=True,
    )

    product_type: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="DRAFT",
        server_default="DRAFT",
        index=True,
    )

    requires_shipping: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    taxable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=1,
        server_default="1",
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
    )

    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "slug",
            name="uq_products_store_slug",
        ),
    )


# ============================================================
# 2. PRODUCT OPTIONS
# ============================================================

class ProductOptionModel(Base):
    __tablename__ = "product_options"

    option_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
    )

    product_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    position: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "name",
            name="uq_product_options_product_name",
        ),
        UniqueConstraint(
            "product_id",
            "position",
            name="uq_product_options_product_position",
        ),
    )


# ============================================================
# 3. PRODUCT OPTION VALUES
# ============================================================

class ProductOptionValueModel(Base):
    __tablename__ = "product_option_values"

    option_value_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
    )

    option_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("product_options.option_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    value: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    position: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )

    metadata_json: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "option_id",
            "value",
            name="uq_product_option_values_option_value",
        ),
    )


# ============================================================
# 4. PRODUCT VARIANTS
# ============================================================

class ProductVariantModel(Base):
    __tablename__ = "product_variants"

    variant_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
    )

    store_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("stores.store_id"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sku: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    barcode: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    option_signature: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    base_price: Mapped[Decimal] = mapped_column(
        Numeric(19, 4),
        nullable=False,
        index=True,
    )

    compare_at_price: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 4),
        nullable=True,
    )

    cost_price: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 4),
        nullable=True,
    )

    currency: Mapped[str] = mapped_column(
        CHAR(3),
        nullable=False,
    )

    weight: Mapped[float | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
    )

    weight_unit: Mapped[str | None] = mapped_column(
        String(8),
        nullable=True,
    )

    length: Mapped[float | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
    )

    width: Mapped[float | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
    )

    height: Mapped[float | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
    )

    dimension_unit: Mapped[str | None] = mapped_column(
        String(8),
        nullable=True,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    inventory_policy: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="DENY",
        server_default="DENY",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=1,
        server_default="1",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
    )

    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "variant_id",
            name="uq_product_variants_product_variant",
        ),
        UniqueConstraint(
            "product_id",
            "option_signature",
            name="uq_product_variants_product_signature",
        ),
        Index(
            "ix_product_variants_sku_store",
            "store_id",
            "sku",
            unique=True,
            postgresql_where=sku.is_not(None),
        ),
    )


# ============================================================
# 5. VARIANT OPTION VALUES
# ============================================================

class VariantOptionValueModel(Base):
    __tablename__ = "variant_option_values"

    variant_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("product_variants.variant_id", ondelete="CASCADE"),
        primary_key=True,
    )

    option_value_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey(
            "product_option_values.option_value_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )


# ============================================================
# 6. MEDIA ASSETS
# ============================================================

class MediaAssetModel(Base):
    __tablename__ = "media_assets"

    media_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
    )

    store_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("stores.store_id"),
        nullable=False,
        index=True,
    )

    media_type: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        index=True,
    )

    storage_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        unique=True,
    )

    public_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    alt_text: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    width: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    height: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )


# ============================================================
# 7. PRODUCT MEDIA
# ============================================================

class ProductMediaModel(Base):
    __tablename__ = "product_media"

    product_media_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
    )

    product_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    variant_id: Mapped[UUID | None] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("product_variants.variant_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    media_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("media_assets.media_id", ondelete="CASCADE"),
        nullable=False,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        index=True,
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )


# ============================================================
# 8. COLLECTIONS
# ============================================================

class CollectionModel(Base):
    __tablename__ = "collections"

    collection_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
    )

    store_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("stores.store_id"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(220),
        nullable=False,
    )

    description_html: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    collection_type: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
    )

    rule_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
    )

    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "slug",
            name="uq_collections_store_slug",
        ),
    )


# ============================================================
# 9. COLLECTION PRODUCTS
# ============================================================

class CollectionProductModel(Base):
    __tablename__ = "collection_products"

    collection_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("collections.collection_id", ondelete="CASCADE"),
        primary_key=True,
    )

    product_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("products.product_id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )


# ============================================================
# 10. TAGS
# ============================================================

class TagModel(Base):
    __tablename__ = "tags"

    tag_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
    )

    store_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("stores.store_id"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "name",
            name="uq_tags_store_name",
        ),
    )


# ============================================================
# 11. PRODUCT TAGS
# ============================================================

class ProductTagModel(Base):
    __tablename__ = "product_tags"

    product_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("products.product_id", ondelete="CASCADE"),
        primary_key=True,
    )

    tag_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("tags.tag_id", ondelete="CASCADE"),
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )


# ============================================================
# 12. METAFIELD DEFINITIONS
# ============================================================

class MetafieldDefinitionModel(Base):
    __tablename__ = "metafield_definitions"

    definition_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
    )

    store_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("stores.store_id"),
        nullable=False,
        index=True,
    )

    resource_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    namespace: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    value_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    validation: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "resource_type",
            "namespace",
            "key",
            name="uq_metafield_definitions_store_resource_namespace_key",
        ),
    )


# ============================================================
# 13. METAFIELDS
# ============================================================

class MetafieldModel(Base):
    __tablename__ = "metafields"

    metafield_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
    )

    definition_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey(
            "metafield_definitions.definition_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    resource_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
    )

    resource_id: Mapped[UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    value_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
    )

    __table_args__ = (
        UniqueConstraint(
            "definition_id",
            "resource_id",
            name="uq_metafields_definition_resource",
        ),
    )