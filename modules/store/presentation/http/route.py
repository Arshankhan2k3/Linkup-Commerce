from fastapi import APIRouter

from modules.store.presentation.http.routes.admin import router as admin_router


router = APIRouter()

router.include_router(admin_router)