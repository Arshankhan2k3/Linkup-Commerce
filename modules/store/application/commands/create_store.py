"""Create store command."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from modules.store.infrastructure.db.models import StoreModel, StoreSettingsModel
from modules.store.infrastructure.db.repository import StoreRepository, StoreSettingsRepository
from shared.domain.ids import generate_uuid


async def create_store(
    *,
    store_repo: StoreRepository,
    settings_repo: StoreSettingsRepository,
    name: str,
    country_code: str,
    default_currency: str = "INR",
    timezone_str: str = "UTC",
    legal_name: str | None = None,
) -> UUID:
    """
    Create a new store + default settings row.
    Returns the new store_id.
    """
    now = datetime.now(timezone.utc)
    store_id = generate_uuid()

    store = StoreModel(
        store_id=store_id,
        name=name,
        legal_name=legal_name,
        default_currency=default_currency,
        country_code=country_code,
        timezone=timezone_str,
        status="ACTIVE",
        version=1,
        created_at=now,
        updated_at=now,
    )
    await store_repo.save(store)

    # Create default settings row (12 attributes)
    setting = StoreSettingsModel(
        settings_id=generate_uuid(),
        store_id=store_id,
        order_prefix="ORD",
        weight_unit="kg",
        dimension_unit="cm",
        tax_inclusive=False,
        allow_guest_checkout=True,
        inventory_policy="DENY",
        checkout_expiry_minutes=30,
        version=1,
        config={},
        updated_at=now,
    )
    await settings_repo.save(setting)

    return store_id