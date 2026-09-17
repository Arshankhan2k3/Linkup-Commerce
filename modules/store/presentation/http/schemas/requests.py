"""Store request schemas — Pydantic v2."""

from __future__ import annotations

import re
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class CreateStoreRequest(BaseModel):
    name: str
    slug: str | None = None
    email: EmailStr | None = None
    country_code: str
    currency: str = "USD"
    timezone: str = "UTC"
    legal_name: str | None = None
    phone: str | None = None

    @field_validator("country_code")
    @classmethod
    def _country_code(cls, v: str) -> str:
        if len(v) != 2:
            raise ValueError("country_code must be 2-letter ISO 3166-1 alpha-2")
        return v.upper()

    @field_validator("currency")
    @classmethod
    def _currency(cls, v: str) -> str:
        if len(v) != 3:
            raise ValueError("currency must be 3-letter ISO 4217 code")
        return v.upper()


class StorePatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    legal_name: str | None = None
    country_code: str | None = None
    timezone: str | None = None
    status: str | None = None

    @field_validator("country_code")
    @classmethod
    def _country_code(cls, v: str | None) -> str | None:
        if v is not None:
            if len(v.strip()) != 2:
                raise ValueError("country_code must be 2-letter ISO 3166-1 alpha-2")
            return v.strip().upper()
        return v

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v is not None:
            upper_v = v.strip().upper()
            if upper_v not in ("ACTIVE", "PAUSED", "CLOSED"):
                raise ValueError("status must be ACTIVE, PAUSED, or CLOSED")
            return upper_v
        return v


# Backward compatibility alias
UpdateStoreRequest = StorePatchRequest


class SettingsPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_prefix: str | None = None
    weight_unit: str | None = None
    dimension_unit: str | None = None
    tax_inclusive: bool | None = None
    allow_guest_checkout: bool | None = None
    inventory_policy: str | None = None
    checkout_expiry_minutes: int | None = None

    @field_validator("inventory_policy")
    @classmethod
    def _inventory_policy(cls, v: str | None) -> str | None:
        if v is not None:
            upper_v = v.strip().upper()
            if upper_v != "DENY":
                raise ValueError("Release 1 accepts inventory_policy=DENY only")
            return upper_v
        return v

    @field_validator("weight_unit")
    @classmethod
    def _weight_unit(cls, v: str | None) -> str | None:
        if v is not None:
            lower_v = v.strip().lower()
            if lower_v not in ("kg", "g", "lb"):
                raise ValueError("weight_unit must be kg, g, or lb")
            return lower_v
        return v

    @field_validator("dimension_unit")
    @classmethod
    def _dimension_unit(cls, v: str | None) -> str | None:
        if v is not None:
            lower_v = v.strip().lower()
            if lower_v not in ("cm", "in"):
                raise ValueError("dimension_unit must be cm or in")
            return lower_v
        return v

    @field_validator("checkout_expiry_minutes")
    @classmethod
    def _expiry(cls, v: int | None) -> int | None:
        if v is not None:
            if v < 1 or v > 1440:
                raise ValueError("checkout_expiry_minutes must be between 1 and 1440")
        return v


# Backward compatibility alias
UpdateStoreSettingsRequest = SettingsPatchRequest


class SalesChannelCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    channel_type: str  # 'STOREFRONT', 'ADMIN', 'MARKETPLACE', 'POS', 'API'
    config: dict = {}

    @field_validator("channel_type")
    @classmethod
    def _channel_type(cls, v: str) -> str:
        upper_v = v.strip().upper()
        if upper_v not in ("STOREFRONT", "ADMIN", "MARKETPLACE", "POS", "API"):
            raise ValueError("channel_type must be STOREFRONT, ADMIN, MARKETPLACE, POS, or API")
        return upper_v


# Backward compatibility alias
CreateSalesChannelRequest = SalesChannelCreateRequest


class SalesChannelPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    status: str | None = None
    config: dict | None = None

    @field_validator("status")
    @classmethod
    def _status(cls, v: str | None) -> str | None:
        if v is not None:
            upper_v = v.strip().upper()
            if upper_v not in ("ACTIVE", "INACTIVE"):
                raise ValueError("status must be ACTIVE or INACTIVE")
            return upper_v
        return v