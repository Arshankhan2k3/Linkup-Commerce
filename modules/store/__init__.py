"""Store module — manages the single-tenant store entity.

This module is responsible for:
- Store lifecycle (create, update, suspend)
- Store settings management (order prefix, tax settings, etc.)
- Sales channel management (online store, POS, API channels)

Architecture layers:
    domain/         — pure Python entities and repository protocols (no frameworks)
    application/    — commands, queries, handlers (no SQLAlchemy)
    infrastructure/ — SQLAlchemy ORM models and concrete repositories
    presentation/   — FastAPI routes and Pydantic schemas
"""
