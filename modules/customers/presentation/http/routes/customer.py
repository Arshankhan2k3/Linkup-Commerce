"""Customer HTTP routes — 12 endpoints.

All routes use async with uow: pattern. No db.commit() ever.
store_id comes from settings.STORE_ID (single-tenant deployment).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import settings
from app.db.session import SqlAlchemyUnitOfWork, get_uow
from modules.customers.application.commands.create_customer import create_customer
from modules.customers.infrastructure.db.models import (
    CustomerAddressModel,
    CustomerConsentModel,
    CustomerNoteModel,
)
from modules.customers.infrastructure.db.repository import (
    CustomerAddressRepository,
    CustomerConsentRepository,
    CustomerNoteRepository,
    CustomerRepository,
)
from modules.customers.presentation.http.schemas.requests import (
    CreateAddressRequest,
    CreateCustomerRequest,
    CreateNoteRequest,
    UpdateConsentRequest,
    UpdateCustomerRequest,
)
from modules.customers.presentation.http.schemas.responses import (
    CustomerAddressResponse,
    CustomerConsentResponse,
    CustomerNoteResponse,
    CustomerResponse,
)
from shared.domain.ids import generate_uuid

router = APIRouter(prefix="/customers", tags=["Customers"])


def _get_store_id() -> UUID:
    sid = settings.STORE_ID
    if not sid:
        raise HTTPException(status_code=503, detail="Store not provisioned")
    return UUID(sid)


# ---------------------------------------------------------------------------
# Customer CRUD
# ---------------------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED, response_model=CustomerResponse)
async def create_customer_endpoint(
    body: CreateCustomerRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> CustomerResponse:
    store_id = _get_store_id()
    async with uow:
        repo = CustomerRepository(uow.session)
        customer_id = await create_customer(
            customer_repo=repo,
            store_id=store_id,
            first_name=body.first_name,
            last_name=body.last_name,
            email=str(body.email) if body.email else None,
            phone=body.phone,
            password=body.password,
            accepts_marketing=body.accepts_marketing,
        )
        await uow.commit()
        customer = await repo.get_by_id(customer_id)
    return CustomerResponse.model_validate(customer)


@router.get("", response_model=list[CustomerResponse])
async def list_customers(
    limit: int = 20,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> list[CustomerResponse]:
    store_id = _get_store_id()
    async with uow:
        customers = await CustomerRepository(uow.session).list_by_store(store_id, limit=limit)
    return [CustomerResponse.model_validate(c) for c in customers]


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> CustomerResponse:
    async with uow:
        customer = await CustomerRepository(uow.session).get_by_id(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return CustomerResponse.model_validate(customer)


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: UUID,
    body: UpdateCustomerRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> CustomerResponse:
    async with uow:
        repo = CustomerRepository(uow.session)
        customer = await repo.get_by_id(customer_id)
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found")

        for field, value in body.model_dump(exclude_none=True).items():
            setattr(customer, field, value)
        customer.updated_at = datetime.now(timezone.utc)

        await repo.save(customer)
        await uow.commit()
    return CustomerResponse.model_validate(customer)


@router.delete("/{customer_id}", response_model=CustomerResponse)
async def disable_customer(
    customer_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> CustomerResponse:
    async with uow:
        repo = CustomerRepository(uow.session)
        customer = await repo.get_by_id(customer_id)
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        customer.status = "disabled"
        customer.updated_at = datetime.now(timezone.utc)
        await repo.save(customer)
        await uow.commit()
    return CustomerResponse.model_validate(customer)


# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------

@router.get("/{customer_id}/addresses", response_model=list[CustomerAddressResponse])
async def list_addresses(
    customer_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> list[CustomerAddressResponse]:
    async with uow:
        addresses = await CustomerAddressRepository(uow.session).list_by_customer(customer_id)
    return [CustomerAddressResponse.model_validate(a) for a in addresses]


@router.post("/{customer_id}/addresses", status_code=status.HTTP_201_CREATED, response_model=CustomerAddressResponse)
async def add_address(
    customer_id: UUID,
    body: CreateAddressRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> CustomerAddressResponse:
    store_id = _get_store_id()
    async with uow:
        addr_repo = CustomerAddressRepository(uow.session)
        if body.is_default:
            await addr_repo.clear_default(customer_id)

        address = CustomerAddressModel(
            address_id=generate_uuid(),
            customer_id=customer_id,
            store_id=store_id,
            first_name=body.first_name,
            last_name=body.last_name,
            company=body.company,
            address_line1=body.address_line1,
            address_line2=body.address_line2,
            city=body.city,
            province=body.province,
            country_code=body.country_code.upper(),
            postal_code=body.postal_code,
            phone=body.phone,
            is_default=body.is_default,
            created_at=datetime.now(timezone.utc),
        )
        await addr_repo.save(address)
        await uow.commit()
    return CustomerAddressResponse.model_validate(address)


@router.delete("/{customer_id}/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(
    customer_id: UUID,
    address_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> None:
    async with uow:
        repo = CustomerAddressRepository(uow.session)
        address = await repo.get_by_id(address_id)
        if address is None or address.customer_id != customer_id:
            raise HTTPException(status_code=404, detail="Address not found")
        await repo.delete(address)
        await uow.commit()


# ---------------------------------------------------------------------------
# Consents
# ---------------------------------------------------------------------------

@router.get("/{customer_id}/consents", response_model=list[CustomerConsentResponse])
async def list_consents(
    customer_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> list[CustomerConsentResponse]:
    async with uow:
        consents = await CustomerConsentRepository(uow.session).list_by_customer(customer_id)
    return [CustomerConsentResponse.model_validate(c) for c in consents]


@router.put("/{customer_id}/consents", response_model=CustomerConsentResponse)
async def update_consent(
    customer_id: UUID,
    body: UpdateConsentRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> CustomerConsentResponse:
    async with uow:
        repo = CustomerConsentRepository(uow.session)
        consent = await repo.get_by_customer_and_type(customer_id, body.consent_type)
        now = datetime.now(timezone.utc)
        if consent is None:
            consent = CustomerConsentModel(
                consent_id=generate_uuid(),
                customer_id=customer_id,
                consent_type=body.consent_type,
                granted=body.granted,
                granted_at=now,
            )
        else:
            consent.granted = body.granted
            consent.granted_at = now
        await repo.save(consent)
        await uow.commit()
    return CustomerConsentResponse.model_validate(consent)


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

@router.get("/{customer_id}/notes", response_model=list[CustomerNoteResponse])
async def list_notes(
    customer_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> list[CustomerNoteResponse]:
    async with uow:
        notes = await CustomerNoteRepository(uow.session).list_by_customer(customer_id)
    return [CustomerNoteResponse.model_validate(n) for n in notes]


@router.post("/{customer_id}/notes", status_code=status.HTTP_201_CREATED, response_model=CustomerNoteResponse)
async def add_note(
    customer_id: UUID,
    body: CreateNoteRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> CustomerNoteResponse:
    store_id = _get_store_id()
    async with uow:
        note = CustomerNoteModel(
            note_id=generate_uuid(),
            customer_id=customer_id,
            store_id=store_id,
            body=body.body,
            created_by_staff_id=None,
            created_at=datetime.now(timezone.utc),
        )
        await CustomerNoteRepository(uow.session).save(note)
        await uow.commit()
    return CustomerNoteResponse.model_validate(note)