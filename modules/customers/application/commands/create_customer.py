"""Create customer command."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.core.security import hash_password
from modules.customers.infrastructure.db.models import CustomerModel
from modules.customers.infrastructure.db.repository import CustomerRepository
from shared.domain.exceptions import DuplicateResourceError
from shared.domain.ids import generate_uuid

async def create_customer(
    *,
    customer_repo: CustomerRepository,
    store_id: UUID,
    first_name: str,
    last_name: str,
    email: str | None = None,
    phone: str | None = None,
    password: str | None = None,
    accepts_marketing: bool = False,
) -> UUID:
    """Create a new customer.

    Returns customer_id.
    Raises DuplicateResourceError if email already exists for this store.
    """
    if email:
        existing = await customer_repo.get_by_email_and_store(email=email, store_id=store_id)
        if existing is not None:
            raise DuplicateResourceError(f"Customer with email '{email}' already exists", code="DUPLICATE_RESOURCE")

    now = datetime.now(timezone.utc)
    customer_id = generate_uuid()

    password_hash: str | None = None
    if password:
        password_hash = hash_password(password)

    customer = CustomerModel(
        customer_id=customer_id,
        store_id=store_id,
        email=email,
        phone=phone,
        first_name=first_name,
        last_name=last_name,
        password_hash=password_hash,
        status="active",
        accepts_marketing=accepts_marketing,
        version=0,
        created_at=now,
        updated_at=now,
    )
    await customer_repo.save(customer)
    return customer_id