"""Request context — ContextVar storage + ASGI middleware.

Provides a lightweight, async-safe request context that carries:
- request_id   : unique per request (UUID, sourced from X-Request-ID header or generated)
- correlation_id: optional cross-service trace ID (X-Correlation-ID header)

Usage
-----
From anywhere in the call stack during a request:

    from app.core.request_context import get_request_id, get_correlation_id

The middleware automatically echoes X-Request-ID back in the response.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# ---------------------------------------------------------------------------
# Context variables (per-task, async-safe)
# ---------------------------------------------------------------------------

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")
_correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def get_request_id() -> str:
    """Return the current request's ID, or empty string outside a request."""
    return _request_id_var.get()


def get_correlation_id() -> str:
    """Return the current correlation ID, or empty string if not set."""
    return _correlation_id_var.get()


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class RequestContextMiddleware(BaseHTTPMiddleware):
    """Populate ContextVars for each incoming request.

    - Reads ``X-Request-ID`` header; generates a UUID if absent.
    - Reads ``X-Correlation-ID`` header; defaults to the request ID if absent.
    - Echoes ``X-Request-ID`` in every response.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = (
            request.headers.get("X-Request-ID") or str(uuid.uuid4())
        )
        correlation_id = (
            request.headers.get("X-Correlation-ID") or request_id
        )

        token_rid = _request_id_var.set(request_id)
        token_cid = _correlation_id_var.set(correlation_id)

        try:
            response: Response = await call_next(request)
        finally:
            _request_id_var.reset(token_rid)
            _correlation_id_var.reset(token_cid)

        response.headers["X-Request-ID"] = request_id
        return response
