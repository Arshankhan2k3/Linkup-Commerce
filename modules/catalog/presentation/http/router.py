from fastapi import APIRouter

from modules.catalog.presentation.http.routes.admin import router as admin_router
from modules.catalog.presentation.http.routes.storefront import router as storefront_router

router = APIRouter()

router.include_router(storefront_router)
router.include_router(admin_router)