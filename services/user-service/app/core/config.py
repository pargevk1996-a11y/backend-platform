from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Service settings loaded from user-service .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "user-service"
    service_env: Literal["development", "staging", "production"] = "development"
    service_port: int = 8002
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    trusted_proxy_ips: Annotated[list[str], NoDecode] = Field(default_factory=list)

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")

    jwt_algorithm: str = "RS256"
    jwt_issuer: str = "backend-platform"
    jwt_audience: str = "backend-clients"
    jwt_public_key: SecretStr = Field(alias="JWT_PUBLIC_KEY")
    privacy_key_pepper: SecretStr = Field(alias="PRIVACY_KEY_PEPPER")

    rate_limit_profile_write_per_minute: int = 30
    rate_limit_roles_write_per_minute: int = 10

    health_timeout_seconds: int = 2

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _parse_origins(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("trusted_proxy_ips", mode="before")
    @classmethod
    def _parse_trusted_proxy_ips(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("privacy_key_pepper")
    @classmethod
    def _validate_pepper_length(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < MIN_SECRET_LENGTH:
            raise ValueError(f"PRIVACY_KEY_PEPPER must be at least {MIN_SECRET_LENGTH} characters")
        return value

    @property
    def jwt_public_key_value(self) -> str:
        return self.jwt_public_key.get_secret_value()

    @property
    def privacy_key_pepper_value(self) -> str:
        return self.privacy_key_pepper.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
