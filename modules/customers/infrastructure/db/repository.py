"""Customer repository — SQLAlchemy implementations. No commit() calls inside repository methods."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    CustomerAddressModel,
    CustomerConsentModel,
    CustomerModel,
    CustomerNoteModel,
)


class CustomerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, customer_id: UUID) -> CustomerModel | None:
        result = await self._session.execute(
            select(CustomerModel).where(CustomerModel.customer_id == customer_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email_and_store(self, email: str, store_id: UUID) -> CustomerModel | None:
        result = await self._session.execute(
            select(CustomerModel).where(
                CustomerModel.email == email,
                CustomerModel.store_id == store_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_email_or_phone_and_store(self, identifier: str, store_id: UUID) -> CustomerModel | None:
        result = await self._session.execute(
            select(CustomerModel).where(
                CustomerModel.store_id == store_id,
                or_(CustomerModel.email == identifier, CustomerModel.phone == identifier),
            )
        )
        return result.scalar_one_or_none()

    async def search_by_store(
        self,
        store_id: UUID,
        query: str | None = None,
        status: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 50,
        after_id: UUID | None = None,
    ) -> list[CustomerModel]:
        q = select(CustomerModel).where(CustomerModel.store_id == store_id)
        if query:
            pattern = f"%{query}%"
            q = q.where(
                or_(
                    CustomerModel.email.ilike(pattern),
                    CustomerModel.phone.ilike(pattern),
                    CustomerModel.first_name.ilike(pattern),
                    CustomerModel.last_name.ilike(pattern),
                )
            )
        if status:
            q = q.where(CustomerModel.status == status)
        if created_from:
            q = q.where(CustomerModel.created_at >= created_from)
        if created_to:
            q = q.where(CustomerModel.created_at <= created_to)
        if after_id is not None:
            q = q.where(CustomerModel.customer_id > after_id)

        q = q.order_by(CustomerModel.customer_id).limit(limit)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def count_by_store(self, store_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(CustomerModel).where(CustomerModel.store_id == store_id)
        )
        return result.scalar_one()

    async def save(self, customer: CustomerModel) -> None:
        self._session.add(customer)
        await self._session.flush()


class CustomerAddressRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, address_id: UUID) -> CustomerAddressModel | None:
        result = await self._session.execute(
            select(CustomerAddressModel).where(CustomerAddressModel.address_id == address_id)
        )
        return result.scalar_one_or_none()

    async def list_by_customer(self, customer_id: UUID) -> list[CustomerAddressModel]:
        result = await self._session.execute(
            select(CustomerAddressModel).where(CustomerAddressModel.customer_id == customer_id)
        )
        return list(result.scalars().all())

    async def save(self, address: CustomerAddressModel) -> None:
        self._session.add(address)
        await self._session.flush()

    async def delete(self, address: CustomerAddressModel) -> None:
        await self._session.delete(address)
        await self._session.flush()

    async def clear_default(self, customer_id: UUID) -> None:
        await self._session.execute(
            update(CustomerAddressModel)
            .where(CustomerAddressModel.customer_id == customer_id)
            .values(is_default=False)
        )


class CustomerConsentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_customer(self, customer_id: UUID) -> list[CustomerConsentModel]:
        result = await self._session.execute(
            select(CustomerConsentModel)
            .where(CustomerConsentModel.customer_id == customer_id)
            .order_by(CustomerConsentModel.occurred_at.desc())
        )
        return list(result.scalars().all())

    async def save(self, consent: CustomerConsentModel) -> None:
        self._session.add(consent)
        await self._session.flush()


class CustomerNoteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_customer(self, customer_id: UUID) -> list[CustomerNoteModel]:
        result = await self._session.execute(
            select(CustomerNoteModel)
            .where(CustomerNoteModel.customer_id == customer_id)
            .order_by(CustomerNoteModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def save(self, note: CustomerNoteModel) -> None:
        self._session.add(note)
        await self._session.flush()