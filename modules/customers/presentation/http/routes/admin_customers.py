"""Admin Customer HTTP routes — list/search, detail/history, update status/metadata/notes."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.db.session import SqlAlchemyUnitOfWork, get_uow
from modules.customers.infrastructure.db.models import CustomerNoteModel
from modules.customers.infrastructure.db.repository import (
    CustomerAddressRepository,
    CustomerConsentRepository,
    CustomerNoteRepository,
    CustomerRepository,
)
from modules.customers.presentation.http.schemas.requests import AdminCustomerUpdateRequest
from modules.customers.presentation.http.schemas.responses import (
    AddressResponse,
    ConsentResponse,
    CustomerDetailResponse,
    CustomerNoteResponse,
    CustomerResponse,
)
from modules.iam.presentation.http.deps import (
    get_current_user_payload,
    require_permission,
)
from shared.domain.ids import generate_uuid

router = APIRouter(prefix="/admin/customers", tags=["Admin Customer Management"])


def _get_store_id() -> UUID:
    sid = settings.STORE_ID
    if not sid:
        raise HTTPException(status_code=503, detail="Store not provisioned")
    return UUID(sid)


@router.get("", response_model=list[CustomerResponse], dependencies=[Depends(require_permission("customers.read"))])
async def search_customers(
    query: str | None = None,
    status_filter: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = 50,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> list[CustomerResponse]:
    store_id = _get_store_id()
    async with uow:
        repo = CustomerRepository(uow.session)
        customers = await repo.search_by_store(
            store_id=store_id,
            query=query,
            status=status_filter,
            created_from=created_from,
            created_to=created_to,
            limit=limit,
        )
    return [CustomerResponse.model_validate(c) for c in customers]


@router.get("/{customer_id}", response_model=CustomerDetailResponse, dependencies=[Depends(require_permission("customers.read"))])
async def get_customer_detail(
    customer_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> CustomerDetailResponse:
    store_id = _get_store_id()
    async with uow:
        customer_repo = CustomerRepository(uow.session)
        customer = await customer_repo.get_by_id(customer_id)
        if customer is None or customer.store_id != store_id:
            raise HTTPException(status_code=404, detail="Customer not found")

        addresses = await CustomerAddressRepository(uow.session).list_by_customer(customer_id)
        consents = await CustomerConsentRepository(uow.session).list_by_customer(customer_id)
        notes = await CustomerNoteRepository(uow.session).list_by_customer(customer_id)

    return CustomerDetailResponse(
        customer=CustomerResponse.model_validate(customer),
        addresses=[AddressResponse.model_validate(a) for a in addresses],
        consents=[ConsentResponse.model_validate(c) for c in consents],
        notes=[CustomerNoteResponse.model_validate(n) for n in notes],
    )


@router.patch("/{customer_id}", response_model=CustomerResponse, dependencies=[Depends(require_permission("customers.write"))])
async def update_customer_by_admin(
    customer_id: UUID,
    body: AdminCustomerUpdateRequest,
    payload: dict = Depends(get_current_user_payload),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
) -> CustomerResponse:
    store_id = _get_store_id()
    staff_member_id_str = payload.get("staff_member_id")
    actor_staff_id = UUID(staff_member_id_str) if staff_member_id_str else None

    async with uow:
        customer_repo = CustomerRepository(uow.session)
        customer = await customer_repo.get_by_id(customer_id)
        if customer is None or customer.store_id != store_id:
            raise HTTPException(status_code=404, detail="Customer not found")

        if body.first_name is not None:
            customer.first_name = body.first_name
        if body.last_name is not None:
            customer.last_name = body.last_name
        if body.phone is not None:
            customer.phone = body.phone
        if body.status is not None:
            customer.status = body.status

        customer.updated_at = datetime.now(timezone.utc)
        await customer_repo.save(customer)

        if body.note:
            note_obj = CustomerNoteModel(
                customer_note_id=generate_uuid(),
                customer_id=customer_id,
                actor_staff_member_id=actor_staff_id,
                body=body.note,
                created_at=datetime.now(timezone.utc),
            )
            await CustomerNoteRepository(uow.session).save(note_obj)
        await uow.commit()

    return CustomerResponse.model_validate(customer)
