"""Query + QueryHandler protocols — shared application layer.

Queries are read-only operations that return data without modifying state.
QueryHandlers must NEVER call UnitOfWork.commit().
"""

from __future__ import annotations

from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

# ---------------------------------------------------------------------------
# Type variables
# ---------------------------------------------------------------------------

Q = TypeVar("Q", contravariant=True)  # Query input
R = TypeVar("R", covariant=True)      # Query result


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------

class Query:
    """Marker base class for all query objects.

    Subclass this for every distinct read operation.  Instances are
    plain dataclasses or frozen Pydantic models — no behaviour.
    """


@runtime_checkable
class QueryHandler(Protocol[Q, R]):
    """Protocol every query handler must satisfy.

    Type parameters
    ---------------
    Q : Query   — the input query type
    R : Any     — the result type (domain entity, DTO, paginated list, …)

    Rules
    -----
    - Handlers are *read-only*: no commit(), no state mutation.
    - Handlers may use read-only DB sessions or cache reads.
    - Never import from FastAPI, presentation layer, or UnitOfWork inside a handler.
    """

    async def handle(self, query: Q) -> R:  # type: ignore[override]
        ...
