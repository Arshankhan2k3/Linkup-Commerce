"""IAM module router — aggregates all IAM HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter

from modules.iam.presentation.http.routes.admin_roles import router as admin_roles_router
from modules.iam.presentation.http.routes.admin_staff import router as admin_staff_router
from modules.iam.presentation.http.routes.auth import router as auth_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(admin_staff_router)
router.include_router(admin_roles_router)