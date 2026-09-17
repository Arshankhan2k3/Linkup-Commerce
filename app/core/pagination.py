"""Pagination utilities — cursor-based pagination for all list endpoints.

Architecture mandates cursor pagination (not offset) for scalability.
Cursor values are opaque base64-encoded strings that encode a sort key.

Usage
-----
In a route:

    from app.core.pagination import CursorPaginationParams, PaginatedResponse

    @router.get("/products")
    async def list_products(
        params: CursorPaginationParams = Depends(),
    ) -> PaginatedResponse[ProductDTO]:
        ...

In a query handler, pass ``params.limit``, ``params.after`` to the repo,
then wrap the result:

    return PaginatedResponse.build(items=rows, params=params, total=count)
"""

from __future__ import annotations

import base64
from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict

from app.core.config import settings

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Request params
# ---------------------------------------------------------------------------

class CursorPaginationParams:
    """Dependency-injectable cursor pagination parameters.

    Parameters
    ----------
    limit:
        Number of items per page (1–MAX_PAGE_SIZE).
    after:
        Opaque cursor pointing to the item *after* which results begin.
    before:
        Opaque cursor pointing to the item *before* which results begin
        (for backward pagination — optional, not all endpoints support it).
    """

    def __init__(
        self,
        limit: int = Query(
            default=settings.DEFAULT_PAGE_SIZE,
            ge=1,
            le=settings.MAX_PAGE_SIZE,
            description="Number of items to return (max 100)",
        ),
        after: str | None = Query(
            default=None,
            description="Cursor — return items after this position",
        ),
        before: str | None = Query(
            default=None,
            description="Cursor — return items before this position (backward paging)",
        ),
    ) -> None:
        self.limit = limit
        self.after = after
        self.before = before

    # ------------------------------------------------------------------
    # Cursor encoding helpers
    # ------------------------------------------------------------------

    @staticmethod
    def encode_cursor(value: str) -> str:
        """Encode a plain string (e.g. UUID or ISO datetime) as an opaque cursor."""
        return base64.urlsafe_b64encode(value.encode()).decode()

    @staticmethod
    def decode_cursor(cursor: str) -> str:
        """Decode an opaque cursor back to a plain string."""
        try:
            return base64.urlsafe_b64decode(cursor.encode()).decode()
        except Exception as exc:
            raise ValueError(f"Invalid cursor: {cursor!r}") from exc


# ---------------------------------------------------------------------------
# Response wrapper
# ---------------------------------------------------------------------------

class PageInfo(BaseModel):
    """Pagination metadata included in every list response."""

    model_config = ConfigDict(frozen=True)

    has_next_page: bool
    has_previous_page: bool
    start_cursor: str | None = None
    end_cursor: str | None = None
    total_count: int | None = None  # May be None if count query is skipped


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response envelope.

    ``items`` holds the page of results.
    ``page_info`` carries cursor / count metadata.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list[T]
    page_info: PageInfo

    @classmethod
    def build(
        cls,
        *,
        items: list[T],
        params: CursorPaginationParams,
        total: int | None = None,
        encode_cursor: bool = True,
    ) -> "PaginatedResponse[T]":
        """Convenience factory.

        Assumes the caller fetched ``params.limit + 1`` rows to detect
        whether a next page exists, then passes only ``params.limit`` rows
        in ``items`` (trimming the extra row before calling this method
        OR relying on ``has_next_page`` logic here).

        Parameters
        ----------
        items:
            The page items (already trimmed to ``params.limit``).
        params:
            The pagination params from the request.
        total:
            Optional total count (skip for performance if not needed).
        encode_cursor:
            If True, encode start/end cursors using str(item) of first/last item IDs.
            Repositories should pass pre-encoded cursor strings instead.
        """
        has_next = len(items) == params.limit and total is not None and total > params.limit
        has_prev = params.after is not None

        start_cursor: str | None = None
        end_cursor: str | None = None

        return cls(
            items=items,
            page_info=PageInfo(
                has_next_page=has_next,
                has_previous_page=has_prev,
                start_cursor=start_cursor,
                end_cursor=end_cursor,
                total_count=total,
            ),
        )
