"""Global error envelope and exception handlers.

Every error response from the API follows this structure:

    {
        "error": {
            "code": "ENTITY_NOT_FOUND",
            "message": "Customer not found",
            "details": []
        },
        "meta": {
            "request_id": "01926..."
        }
    }

Register `install_exception_handlers(app)` in app/main.py.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from shared.domain.exceptions import (
    ConcurrencyError,
    DomainError,
    DuplicateResourceError,
    EntityNotFoundError,
    InvariantViolationError,
    UnauthorizedActionError,
)

from .request_context import get_request_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: list[Any] | None = None,
    request_id: str = "",
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
            },
            "meta": {
                "request_id": request_id,
            },
        },
    )


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def _domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Map domain exceptions to HTTP responses."""
    rid = get_request_id()

    if isinstance(exc, EntityNotFoundError):
        return _error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code=exc.code,
            message=str(exc),
            request_id=rid,
        )
    if isinstance(exc, DuplicateResourceError):
        return _error_response(
            status_code=status.HTTP_409_CONFLICT,
            code=exc.code,
            message=str(exc),
            request_id=rid,
        )
    if isinstance(exc, UnauthorizedActionError):
        return _error_response(
            status_code=status.HTTP_403_FORBIDDEN,
            code=exc.code,
            message=str(exc),
            request_id=rid,
        )
    if isinstance(exc, ConcurrencyError):
        return _error_response(
            status_code=status.HTTP_409_CONFLICT,
            code=exc.code,
            message=str(exc),
            request_id=rid,
        )
    if isinstance(exc, InvariantViolationError):
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=exc.code,
            message=str(exc),
            request_id=rid,
        )
    # Generic domain error fallback
    return _error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        code=exc.code,
        message=str(exc),
        request_id=rid,
    )


async def _validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {
            "field": ".".join(str(loc) for loc in err["loc"]),
            "message": err["msg"],
            "type": err["type"],
        }
        for err in exc.errors()
    ]
    return _error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=details,
        request_id=get_request_id(),
    )


async def _http_error_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code_map: dict[int, str] = {
        400: "BAD_REQUEST",
        401: "UNAUTHENTICATED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_SERVER_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }
    code = code_map.get(exc.status_code, "HTTP_ERROR")
    return _error_response(
        status_code=exc.status_code,
        code=code,
        message=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
        request_id=get_request_id(),
    )


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # In production, do NOT expose internal details
    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred",
        request_id=get_request_id(),
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def install_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI application."""
    app.add_exception_handler(DomainError, _domain_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_error_handler)
