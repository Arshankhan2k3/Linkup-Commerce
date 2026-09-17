"""Customer module router — aggregates storefront customer and admin customer routes."""

from __future__ import annotations

from fastapi import APIRouter

from modules.customers.presentation.http.routes.admin_customers import router as admin_customers_router
from modules.customers.presentation.http.routes.storefront_customers import (
    router as storefront_customers_router,
)

router = APIRouter()
router.include_router(storefront_customers_router)
router.include_router(admin_customers_router)