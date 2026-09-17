"""Customer HTTP schemas — request models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, EmailStr


class CustomerRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    phone: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class CustomerLoginRequest(BaseModel):
    email_or_phone: str
    password: str


class CustomerProfileUpdateRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None


class AddressInput(BaseModel):
    label: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    line1: str
    line2: str | None = None
    city: str
    state: str
    postal_code: str
    country_code: str  # 2 chars ISO
    is_default: bool = False


class AddressPatch(BaseModel):
    label: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country_code: str | None = None
    is_default: bool | None = None


class ConsentRequest(BaseModel):
    channel: str  # EMAIL, SMS, WHATSAPP
    purpose: str  # MARKETING, PROMOTIONAL, NEWSLETTER
    state: str  # SUBSCRIBED, UNSUBSCRIBED
    source: str | None = None
    metadata: dict[str, Any] = {}


class AdminCustomerUpdateRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    status: str | None = None
    note: str | None = None