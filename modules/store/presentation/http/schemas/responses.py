"""Store response schemas — Pydantic v2."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StorefrontStoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    store_id: UUID
    name: str
    currency: str
    country: str
    timezone: str
    public_settings: dict = Field(default_factory=dict)


class AdminStoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    store_id: UUID
    name: str
    legal_name: str | None = None
    country_code: str
    country: str | None = None  # alias for country_code if needed
    currency: str
    default_currency: str
    timezone: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


# Alias for backwards compatibility
StoreResponse = AdminStoreResponse


class StoreSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    setting_id: UUID
    store_id: UUID
    order_prefix: str
    weight_unit: str
    dimension_unit: str
    tax_inclusive: bool
    allow_guest_checkout: bool
    inventory_policy: str
    checkout_expiry_minutes: int
    version: int
    config: dict = Field(default_factory=dict)
    updated_at: datetime


class SalesChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    channel_id: UUID
    store_id: UUID
    name: str
    channel_type: str
    status: str
    config: dict = Field(default_factory=dict)
    version: int
    created_at: datetime

    @property
    def is_active(self) -> bool:
        return self.status == "ACTIVE"


class PageInfo(BaseModel):
    has_next_page: bool = False
    end_cursor: str | None = None


class SalesChannelConnection(BaseModel):
    items: list[SalesChannelResponse] = Field(default_factory=list)
    page_info: PageInfo = Field(default_factory=PageInfo)