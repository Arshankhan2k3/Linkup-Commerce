

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import (
    CHAR,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    BigInteger,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StoreModel(Base):
    __tablename__ = "stores"

    store_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        comment="Primary store identifier.",
    )
    name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        comment="Merchant/store display name.",
    )
    legal_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Registered business name.",
    )
    default_currency: Mapped[str] = mapped_column(
        CHAR(3),
        nullable=False,
        server_default="INR",
        comment="ISO currency such as INR.",
    )
    country_code: Mapped[str] = mapped_column(
        CHAR(2),
        nullable=False,
        comment="Primary ISO country code.",
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default="UTC",
        comment="Store operating timezone.",
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        server_default="ACTIVE",
        index=True,
        comment="ACTIVE, PAUSED, CLOSED.",
    )
    version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default="1",
        default=1,
        comment="Optimistic concurrency version for admin edits.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        index=True,
        comment="Creation time UTC.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
        comment="Last update UTC.",
    )

    @property
    def currency(self) -> str:
        return self.default_currency

    @currency.setter
    def currency(self, val: str) -> None:
        self.default_currency = val

    # Relationships
    settings: Mapped[StoreSettingsModel | None] = relationship(
        "StoreSettingsModel",
        back_populates="store",
        uselist=False,
        lazy="raise",
        cascade="all, delete-orphan",
    )
    channels: Mapped[list[SalesChannelModel]] = relationship(
        "SalesChannelModel",
        back_populates="store",
        lazy="raise",
        cascade="all, delete-orphan",
    )


class StoreSettingsModel(Base):
    """ORM model for the ``store_settings`` table (12 attributes)."""

    __tablename__ = "store_settings"

    settings_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        comment="Settings row id.",
    )
    store_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("stores.store_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        comment="One settings row per store.",
    )
    order_prefix: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="ORD",
        comment="Human order number prefix.",
    )
    weight_unit: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        server_default="kg",
        comment="kg, g, lb.",
    )
    dimension_unit: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        server_default="cm",
        comment="cm, in.",
    )
    tax_inclusive: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Whether catalog price already contains tax.",
    )
    allow_guest_checkout: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="Guest checkout switch.",
    )
    inventory_policy: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        server_default="DENY",
        comment="Release 1 supports DENY only.",
    )
    checkout_expiry_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="30",
        comment="Reservation/checkout lifetime.",
    )
    version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default="1",
        default=1,
        comment="Optimistic concurrency version for settings edits.",
    )
    config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        default=dict,
        comment="Low-risk extensible flags.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
        comment="Last change.",
    )

    @property
    def setting_id(self) -> pg.UUID:
        return self.settings_id

    @setting_id.setter
    def setting_id(self, val: pg.UUID) -> None:
        self.settings_id = val

    store: Mapped[StoreModel] = relationship(
        "StoreModel",
        back_populates="settings",
        lazy="raise",
    )


class SalesChannelModel(Base):
    """ORM model for the ``sales_channels`` table (8 attributes)."""

    __tablename__ = "sales_channels"

    channel_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        comment="Channel id.",
    )
    store_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("stores.store_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Owning store.",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Online Store, Admin Draft, Instagram, etc.",
    )
    channel_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        comment="STOREFRONT, ADMIN, MARKETPLACE, POS, API.",
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        server_default="ACTIVE",
        default="ACTIVE",
        index=True,
        comment="ACTIVE/INACTIVE.",
    )
    config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        default=dict,
        comment="Channel-specific configuration.",
    )
    version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default="1",
        default=1,
        comment="Optimistic concurrency version for admin edits.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        comment="Created time.",
    )

    @property
    def is_active(self) -> bool:
        return self.status == "ACTIVE"

    @is_active.setter
    def is_active(self, val: bool) -> None:
        self.status = "ACTIVE" if val else "INACTIVE"

    store: Mapped[StoreModel] = relationship(
        "StoreModel",
        back_populates="channels",
        lazy="raise",
    )