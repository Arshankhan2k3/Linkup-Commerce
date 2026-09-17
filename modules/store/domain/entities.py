"""Store domain entities — pure Python dataclasses.

All entities use UUID primary keys generated in Python before INSERT.
All datetimes are timezone-aware UTC (datetime with timezone.utc).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID


class StoreStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CLOSED = "CLOSED"


class ChannelType(str, Enum):
    STOREFRONT = "STOREFRONT"
    ADMIN = "ADMIN"
    MARKETPLACE = "MARKETPLACE"
    POS = "POS"
    API = "API"


class ChannelStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


@dataclass(frozen=False, kw_only=True)
class Store:
    store_id: UUID
    name: str
    slug: str | None = None
    legal_name: str | None = None
    email: str | None = None
    phone: str | None = None
    country_code: str
    default_currency: str
    timezone: str
    status: StoreStatus = StoreStatus.ACTIVE
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def currency(self) -> str:
        return self.default_currency

    @currency.setter
    def currency(self, val: str) -> None:
        self.default_currency = val


@dataclass(frozen=False, kw_only=True)
class StoreSettings:
    setting_id: UUID
    store_id: UUID
    order_prefix: str = "ORD"
    weight_unit: str = "kg"
    dimension_unit: str = "cm"
    tax_inclusive: bool = False
    allow_guest_checkout: bool = True
    inventory_policy: str = "DENY"
    checkout_expiry_minutes: int = 30
    version: int = 1
    config: dict = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    @property
    def settings_id(self) -> UUID:
        return self.setting_id


@dataclass(frozen=False, kw_only=True)
class SalesChannel:
    channel_id: UUID
    store_id: UUID
    name: str
    channel_type: ChannelType
    status: ChannelStatus = ChannelStatus.ACTIVE
    config: dict = field(default_factory=dict)
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))