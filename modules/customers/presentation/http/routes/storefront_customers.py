"""Storefront Customer HTTP routes — register, login, me, addresses, consents."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.db.session import SqlAlchemyUnitOfWork, get_uow
from modules.customers.infrastructure.db.models import (
    CustomerAddressModel,
    CustomerConsentModel,
    CustomerModel,
)
from modules.customers.infrastructure.db.repository import (
    CustomerAddressRepository,
    CustomerConsentRepository,
    CustomerRepository,
)
from modules.customers.presentation.http.deps import (
    get_current_customer_id,
)
from modules.customers.presentation.http.schemas.requests import (
    AddressInput,
    AddressPatch,
    ConsentRequest,
    CustomerLoginRequest,
    CustomerProfileUpdateRequest,
    CustomerRegisterRequest,
)
from modules.customers.presentation.http.schemas.responses import (
    AddressResponse,
    ConsentResponse,
    CustomerResponse,
    CustomerSessionResponse,
)
from modules.iam.application.services.token_service import create_customer_access_token
from shared.domain.ids import generate_uuid

router = APIRouter(prefix="/storefront/customers", tags=["Storefront Customers"])


def _get_store_id() -> UUID:
    sid = settings.STORE_ID
    if not sid:
        raise HTTPException(status_code=503, detail="Store not provisioned")
    return UUID(sid)


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=CustomerSessionResponse)
async def register_customer(
    body: CustomerRegisterRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> CustomerSessionResponse:
    store_id = _get_store_id()
    async with uow:
        repo = CustomerRepository(uow.session)
        existing = await repo.get_by_email_and_store(body.email, store_id)
        if existing:
            raise HTTPException(status_code=400, detail="Customer with this email already exists")

        customer = CustomerModel(
            customer_id=generate_uuid(),
            store_id=store_id,
            email=str(body.email),
            phone=body.phone,
            first_name=body.first_name,
            last_name=body.last_name,
            password_hash=hash_password(body.password),
            status="ACTIVE",
            accepts_marketing=False,
            total_spent=0,
            orders_count=0,
        )
        await repo.save(customer)
        await uow.commit()

    token = create_customer_access_token(customer_id=customer.customer_id, store_id=store_id)
    return CustomerSessionResponse(
        access_token=token,
        customer=CustomerResponse.model_validate(customer),
    )


@router.post("/login", response_model=CustomerSessionResponse)
async def login_customer(
    body: CustomerLoginRequest,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> CustomerSessionResponse:
    store_id = _get_store_id()
    async with uow:
        repo = CustomerRepository(uow.session)
        customer = await repo.get_by_email_or_phone_and_store(body.email_or_phone, store_id)
        if customer is None or not customer.password_hash or not verify_password(body.password, customer.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email/phone or password")

        if customer.status != "ACTIVE":
            raise HTTPException(status_code=403, detail="Customer account is disabled")

    token = create_customer_access_token(customer_id=customer.customer_id, store_id=store_id)
    return CustomerSessionResponse(
        access_token=token,
        customer=CustomerResponse.model_validate(customer),
    )


@router.get("/me", response_model=CustomerResponse)
async def get_my_profile(
    customer_id: UUID = Depends(get_current_customer_id),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> CustomerResponse:
    async with uow:
        customer = await CustomerRepository(uow.session).get_by_id(customer_id)
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer profile not found")
    return CustomerResponse.model_validate(customer)


@router.patch("/me", response_model=CustomerResponse)
async def update_my_profile(
    body: CustomerProfileUpdateRequest,
    customer_id: UUID = Depends(get_current_customer_id),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> CustomerResponse:
    async with uow:
        repo = CustomerRepository(uow.session)
        customer = await repo.get_by_id(customer_id)
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer profile not found")

        if body.first_name is not None:
            customer.first_name = body.first_name
        if body.last_name is not None:
            customer.last_name = body.last_name
        if body.phone is not None:
            customer.phone = body.phone
        customer.updated_at = datetime.now(timezone.utc)

        await repo.save(customer)
        await uow.commit()

    return CustomerResponse.model_validate(customer)


@router.get("/me/addresses", response_model=list[AddressResponse])
async def list_my_addresses(
    customer_id: UUID = Depends(get_current_customer_id),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> list[AddressResponse]:
    async with uow:
        addresses = await CustomerAddressRepository(uow.session).list_by_customer(customer_id)
    return [AddressResponse.model_validate(a) for a in addresses]


@router.post("/me/addresses", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)
async def create_my_address(
    body: AddressInput,
    customer_id: UUID = Depends(get_current_customer_id),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> AddressResponse:
    async with uow:
        repo = CustomerAddressRepository(uow.session)
        if body.is_default:
            await repo.clear_default(customer_id)

        address = CustomerAddressModel(
            address_id=generate_uuid(),
            customer_id=customer_id,
            label=body.label,
            first_name=body.first_name,
            last_name=body.last_name,
            phone=body.phone,
            line1=body.line1,
            line2=body.line2,
            city=body.city,
            state=body.state,
            postal_code=body.postal_code,
            country_code=body.country_code.upper(),
            is_default=body.is_default,
        )
        await repo.save(address)
        await uow.commit()

    return AddressResponse.model_validate(address)
@router.patch("/me/addresses/{address_id}", response_model=AddressResponse)
async def update_my_address(
    address_id: UUID,
    body: AddressPatch,
    customer_id: UUID = Depends(get_current_customer_id),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> AddressResponse:
    async with uow:
        repo = CustomerAddressRepository(uow.session)
        address = await repo.get_by_id(address_id)
        if address is None or address.customer_id != customer_id:
            raise HTTPException(status_code=404, detail="Address not found")

        if body.is_default is True:
            await repo.clear_default(customer_id)

        for field, value in body.model_dump(exclude_none=True).items():
            setattr(address, field, value)

        address.updated_at = datetime.now(timezone.utc)
        await repo.save(address)
        await uow.commit()

    return AddressResponse.model_validate(address)


@router.delete("/me/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_address(
    address_id: UUID,
    customer_id: UUID = Depends(get_current_customer_id),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> None:
    async with uow:
        repo = CustomerAddressRepository(uow.session)
        address = await repo.get_by_id(address_id)
        if address is None or address.customer_id != customer_id:
            raise HTTPException(status_code=404, detail="Address not found")

        was_default = address.is_default
        await repo.delete(address)

        if was_default:
            remaining = await repo.list_by_customer(customer_id)
            if remaining:
                remaining[0].is_default = True
                await repo.save(remaining[0])

        await uow.commit()


@router.post("/me/consents", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
async def record_my_consent(
    body: ConsentRequest,
    request: Request,
    customer_id: UUID = Depends(get_current_customer_id),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> ConsentResponse:
    client_ip = request.client.host if request.client else None
    now = datetime.now(timezone.utc)

    async with uow:
        consent_repo = CustomerConsentRepository(uow.session)
        customer_repo = CustomerRepository(uow.session)

        customer = await customer_repo.get_by_id(customer_id)
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found")

        consent = CustomerConsentModel(
            consent_id=generate_uuid(),
            customer_id=customer_id,
            channel=body.channel.upper(),
            purpose=body.purpose.upper(),
            state=body.state.upper(),
            source=body.source,
            ip_address=client_ip,
            occurred_at=now,
            consent_metadata=body.metadata,
        )
        await consent_repo.save(consent)

        # Synchronize marketing consent boolean if email marketing updated
        if body.channel.upper() == "EMAIL" and body.purpose.upper() in ("MARKETING", "PROMOTIONAL", "NEWSLETTER"):
            customer.accepts_marketing = (body.state.upper() == "SUBSCRIBED")
            customer.updated_at = now
            await customer_repo.save(customer)

        await uow.commit()

    return ConsentResponse.model_validate(consent)
