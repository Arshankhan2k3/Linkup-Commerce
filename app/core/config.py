"""Application settings — single source of truth for all configuration.

All values are read from environment variables (or a .env file).
Sensitive defaults are intentionally absent — the app will fail fast
if required secrets are missing in production.
"""

from __future__ import annotations

from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Application metadata
    # ------------------------------------------------------------------
    PROJECT_NAME: str = "LinkUp Commerce Engine"
    VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # ------------------------------------------------------------------
    # CORS / host security
    # ------------------------------------------------------------------
    ALLOWED_HOSTS: list[str] = ["*"]
    ALLOWED_ORIGINS: list[str] = ["*"]

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    DATABASE_URL: str  # asyncpg DSN, e.g. postgresql+asyncpg://user:pw@host/db
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_ECHO: bool = False  # set True only in development

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    REDIS_URL: str  # e.g. redis://localhost:6379/0

    # ------------------------------------------------------------------
    # JWT / Auth
    # ------------------------------------------------------------------
    JWT_SECRET_KEY: str               # 256-bit+ random secret
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ------------------------------------------------------------------
    # Integration security
    # ------------------------------------------------------------------
    INTEGRATION_MASTER_KEY: str = ""  # shared secret for internal service calls

    # ------------------------------------------------------------------
    # Store (single-tenant deployment)
    # ------------------------------------------------------------------
    # Set at deployment time; used to scope all operations automatically.
    STORE_ID: str = ""               # UUID string; empty = not yet provisioned

    # ------------------------------------------------------------------
    # Pagination defaults
    # ------------------------------------------------------------------
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _validate_db_url(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must use the 'postgresql+asyncpg://' scheme "
                "(asyncpg driver required for async SQLAlchemy)"
            )
        return v

    @model_validator(mode="after")
    def _warn_insecure_defaults(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            if not self.JWT_SECRET_KEY:
                raise ValueError("JWT_SECRET_KEY must be set in production")
            if not self.INTEGRATION_MASTER_KEY:
                raise ValueError("INTEGRATION_MASTER_KEY must be set in production")
        return self


settings = Settings()