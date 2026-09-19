from __future__ import annotations

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

from modules.catalog.domain.exceptions import (
    CatalogError,
    CollectionAlreadyExistsError,
    CollectionNotFoundError,
    ConcurrencyError,
    DuplicateSKUError,
    InvalidProductError,
    MediaNotFoundError,
    MetafieldDefinitionNotFoundError,
    MetafieldValidationError,
    OptionNotFoundError,
    ProductAlreadyExistsError,
    ProductNotFoundError,
    PublishProductValidationError,
    VariantAlreadyExistsError,
    VariantNotFoundError,
)


def register_catalog_error_handlers(app) -> None:
    """Register FastAPI global exception handlers for catalog errors."""

    @app.exception_handler(CatalogError)
    async def catalog_error_handler(request: Request, exc: CatalogError) -> JSONResponse:
        status_code = status.HTTP_400_BAD_REQUEST

        if isinstance(exc, (ProductNotFoundError, VariantNotFoundError, CollectionNotFoundError, MetafieldDefinitionNotFoundError, MediaNotFoundError, OptionNotFoundError)):
            status_code = status.HTTP_404_NOT_FOUND
        elif isinstance(exc, (ProductAlreadyExistsError, CollectionAlreadyExistsError, VariantAlreadyExistsError, DuplicateSKUError)):
            status_code = status.HTTP_409_CONFLICT
        elif isinstance(exc, ConcurrencyError):
            status_code = status.HTTP_412_PRECONDITION_FAILED
        elif isinstance(exc, (PublishProductValidationError, MetafieldValidationError, InvalidProductError)):
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY

        return JSONResponse(
            status_code=status_code,
            content={"error": exc.__class__.__name__, "message": str(exc)},
        )
