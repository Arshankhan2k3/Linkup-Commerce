from fastapi import APIRouter

from modules.customers.presentation.http.router import (
    router as customer_router,
)
from modules.iam.presentation.http.router import (
    router as iam_router,
)
from modules.store.presentation.http.router import (
    router as store_router,
)
from modules.catalog.presentation.http.router import router as catalog_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(store_router)
api_router.include_router(iam_router)
api_router.include_router(customer_router)
api_router.include_router(catalog_router)