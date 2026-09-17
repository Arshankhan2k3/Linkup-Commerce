"""Customer ORM models — 4 tables.

Tables
------
customers           — store-scoped buyer profile (14 attributes)
customer_addresses  — reusable saved customer addresses (15 attributes)
customer_consents   — consent/audit ledger for marketing and privacy (9 attributes)
customer_notes      — internal support/merchant notes (5 attributes)
"""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import (
    CHAR,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# CustomerModel
# ---------------------------------------------------------------------------

class CustomerModel(Base, TimestampMixin):
    """Store-scoped buyer/customer profile."""

    __tablename__ = "customers"
    __table_args__ = (
        Index(
            "ix_customers_store_email",
            "store_id",
            "email",
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
        Index("ix_customers_store_id", "store_id"),
        Index("ix_customers_email", "email"),
        Index("ix_customers_phone", "phone"),
        Index("ix_customers_created_at", "created_at"),
    )

    customer_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True), primary_key=True
    )
    store_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("stores.store_id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str | None] = mapped_column(CITEXT, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="ACTIVE")
    accepts_marketing: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    total_spent: Mapped[object] = mapped_column(Numeric(19, 4), nullable=False, server_default="0")
    orders_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_order_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    addresses: Mapped[list[CustomerAddressModel]] = relationship(
        "CustomerAddressModel", back_populates="customer", lazy="raise",
        cascade="all, delete-orphan",
    )
    consents: Mapped[list[CustomerConsentModel]] = relationship(
        "CustomerConsentModel", back_populates="customer", lazy="raise",
        cascade="all, delete-orphan",
    )
    notes: Mapped[list[CustomerNoteModel]] = relationship(
        "CustomerNoteModel", back_populates="customer", lazy="raise",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# CustomerAddressModel
# ---------------------------------------------------------------------------

class CustomerAddressModel(Base, TimestampMixin):
    """Reusable saved customer addresses."""

    __tablename__ = "customer_addresses"
    __table_args__ = (
        Index(
            "ix_customer_addresses_default",
            "customer_id",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
        Index("ix_customer_addresses_customer_id", "customer_id"),
        Index("ix_customer_addresses_postal_code", "postal_code"),
    )

    address_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True), primary_key=True
    )
    customer_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("customers.customer_id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    line1: Mapped[str] = mapped_column(String(255), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(120), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(24), nullable=False)
    country_code: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    # Relationship
    customer: Mapped[CustomerModel] = relationship(
        "CustomerModel", back_populates="addresses", lazy="raise"
    )


# ---------------------------------------------------------------------------
# CustomerConsentModel
# ---------------------------------------------------------------------------

class CustomerConsentModel(Base):
    """Consent/audit ledger for marketing and privacy."""

    __tablename__ = "customer_consents"
    __table_args__ = (
        Index("ix_customer_consents_customer_id", "customer_id"),
        Index("ix_customer_consents_channel", "channel"),
        Index("ix_customer_consents_occurred_at", "occurred_at"),
    )

    consent_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True), primary_key=True
    )
    customer_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("customers.customer_id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(24), nullable=False)
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )
    consent_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default="{}")

    # Relationship
    customer: Mapped[CustomerModel] = relationship(
        "CustomerModel", back_populates="consents", lazy="raise"
    )


# ---------------------------------------------------------------------------
# CustomerNoteModel
# ---------------------------------------------------------------------------

class CustomerNoteModel(Base):
    """Append-only internal support/merchant notes."""

    __tablename__ = "customer_notes"
    __table_args__ = (
        Index("ix_customer_notes_customer_id", "customer_id"),
        Index("ix_customer_notes_created_at", "created_at"),
    )

    customer_note_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True), primary_key=True
    )
    customer_id: Mapped[pg.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("customers.customer_id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_staff_member_id: Mapped[pg.UUID | None] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("staff_members.staff_member_id", ondelete="SET NULL"),
        nullable=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )

    # Relationship
    customer: Mapped[CustomerModel] = relationship(
        "CustomerModel", back_populates="notes", lazy="raise"
    )