from fastapi import APIRouter

from modules.store.presentation.http.routes.admin_channels import (
    router as admin_channels_router,
)
from modules.store.presentation.http.routes.admin_settings import (
    router as admin_settings_router,
)
from modules.store.presentation.http.routes.admin_store import (
    router as admin_store_router,
)
from modules.store.presentation.http.routes.storefront_store import (
    router as storefront_store_router,
)

router = APIRouter()

router.include_router(storefront_store_router)
router.include_router(admin_store_router)
router.include_router(admin_settings_router)
router.include_router(admin_channels_router)