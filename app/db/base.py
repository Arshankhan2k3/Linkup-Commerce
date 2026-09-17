"""SQLAlchemy declarative base + shared column mixins.

All ORM models MUST inherit from ``Base``.
Mutable entity models MUST also mix in ``TimestampMixin`` and ``VersionedMixin``.

Rules
-----
- All timestamps are ``TIMESTAMPTZ`` (timezone-aware) stored in UTC.
- ``version`` column is a ``BIGINT`` optimistic-concurrency counter;
  every ``UPDATE`` must include ``WHERE version = :current_version`` and
  increment by 1.  The Unit-of-Work layer enforces this.
- ``created_at`` is set once on first INSERT and never mutated.
- ``updated_at`` is refreshed on every UPDATE via ``onupdate``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedColumn, mapped_column


def _utcnow() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Single registry for all ORM models in the application."""


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------

class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` TIMESTAMPTZ columns.

    Uses DateTime(timezone=True) which maps to TIMESTAMPTZ in PostgreSQL.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
    )


class VersionedMixin:
    """Adds a ``version`` BIGINT column for optimistic concurrency control.

    Rules
    -----
    - Default is ``0`` on first INSERT.
    - Every UPDATE via a ``Repository`` must:
        1. Include ``WHERE version = <current>`` in the query.
        2. Increment ``version`` by 1.
    - If the WHERE clause matches 0 rows the repository raises ``ConcurrencyError``.

    The column is intentionally NOT auto-incremented by the DB — Python
    controls the counter to keep logic testable without touching the DB.
    """

    version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )