"""LinkUp Commerce Engine — ASGI application entry point.

Middleware registration order (outermost → innermost):
1. TrustedHostMiddleware  — blocks invalid Host headers
2. CORSMiddleware         — handles preflight & CORS headers
3. RequestContextMiddleware — injects X-Request-ID ContextVar

Exception handlers are registered after middleware so they have access
to the RequestContext (e.g. to populate request_id in error envelopes).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import install_exception_handlers
from app.core.request_context import RequestContextMiddleware


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        # Disable default validation exception handler — we install our own.
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    )

    # ------------------------------------------------------------------
    # Middleware (registered in reverse processing order)
    # ------------------------------------------------------------------
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    
    app.add_middleware(RequestContextMiddleware)

    # ------------------------------------------------------------------
    # Exception handlers
    # ------------------------------------------------------------------
    install_exception_handlers(app)

    # ------------------------------------------------------------------
    # Routers
    # ------------------------------------------------------------------
    app.include_router(api_router)

    # ------------------------------------------------------------------
    # Health check (excluded from auth)
    # ------------------------------------------------------------------
    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": settings.VERSION}

    return app


app = create_app()