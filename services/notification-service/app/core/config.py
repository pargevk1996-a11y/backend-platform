from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Notification-service settings loaded from its service-specific .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "notification-service"
    service_env: Literal["development", "staging", "production"] = "development"
    service_port: int = 8003
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    health_timeout_seconds: int = 2

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _parse_origins(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @model_validator(mode="after")
    def _validate_deployed_security(self) -> Settings:
        if self.service_env not in {"staging", "production"}:
            return self
        if not self.cors_allowed_origins:
            raise ValueError("Staging and production require explicit CORS_ALLOWED_ORIGINS")
        if any(origin == "*" for origin in self.cors_allowed_origins):
            raise ValueError("Wildcard CORS origin is not allowed in staging or production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
