from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True)
class DomainEvent:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ProductCreated(DomainEvent):
    product_id: UUID = field(default_factory=uuid4)
    store_id: UUID = field(default_factory=uuid4)
    title: str = ""
    slug: str = ""


@dataclass(frozen=True)
class ProductUpdated(DomainEvent):
    product_id: UUID = field(default_factory=uuid4)
    store_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ProductPublished(DomainEvent):
    product_id: UUID = field(default_factory=uuid4)
    store_id: UUID = field(default_factory=uuid4)
    published_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class VariantCreated(DomainEvent):
    variant_id: UUID = field(default_factory=uuid4)
    product_id: UUID = field(default_factory=uuid4)
    store_id: UUID = field(default_factory=uuid4)
    sku: str | None = None


@dataclass(frozen=True)
class VariantUpdated(DomainEvent):
    variant_id: UUID = field(default_factory=uuid4)
    product_id: UUID = field(default_factory=uuid4)
    store_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class MediaReady(DomainEvent):
    media_id: UUID = field(default_factory=uuid4)
    store_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class CollectionUpdated(DomainEvent):
    collection_id: UUID = field(default_factory=uuid4)
    store_id: UUID = field(default_factory=uuid4)
