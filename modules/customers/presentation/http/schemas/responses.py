"""Customer HTTP schemas — response models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    customer_id: UUID
    store_id: UUID
    email: str | None = None
    phone: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    status: str
    accepts_marketing: bool
    total_spent: Decimal
    orders_count: int
    last_order_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AddressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    address_id: UUID
    customer_id: UUID
    label: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    line1: str
    line2: str | None = None
    city: str
    state: str
    postal_code: str
    country_code: str
    is_default: bool
    created_at: datetime
    updated_at: datetime


class ConsentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    consent_id: UUID
    customer_id: UUID
    channel: str
    purpose: str
    state: str
    source: str | None = None
    ip_address: str | None = None
    occurred_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="consent_metadata")


class CustomerNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    customer_note_id: UUID
    customer_id: UUID
    actor_staff_member_id: UUID | None = None
    body: str
    created_at: datetime


class CustomerSessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    customer: CustomerResponse


class CustomerDetailResponse(BaseModel):
    customer: CustomerResponse
    addresses: list[AddressResponse] = []
    consents: list[ConsentResponse] = []
    notes: list[CustomerNoteResponse] = []