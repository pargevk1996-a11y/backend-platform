from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from shared.config import load_file_backed_env

_FILE_BACKED_FIELDS: dict[str, str] = {
    "jwt_public_key": "JWT_PUBLIC_KEY_FILE",
    "privacy_key_pepper": "PRIVACY_KEY_PEPPER_FILE",
}


MIN_SECRET_LENGTH = 32
ALLOWED_JWT_ALGORITHMS = {
    "HS256",
    "HS384",
    "HS512",
    "RS256",
    "RS384",
    "RS512",
    "ES256",
    "ES384",
    "ES512",
}


class Settings(BaseSettings):
    """Service settings loaded from user-service .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="before")
    @classmethod
    def _merge_file_backed_secrets(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        for field_name, content in load_file_backed_env(_FILE_BACKED_FIELDS).items():
            data[field_name] = content
            data[field_name.upper()] = content
        return data

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

    @field_validator("jwt_algorithm")
    @classmethod
    def _validate_jwt_algorithm(cls, value: str) -> str:
        normalized = value.upper().strip()
        if normalized not in ALLOWED_JWT_ALGORITHMS:
            raise ValueError(f"Unsupported JWT algorithm: {normalized}")
        return normalized

    @field_validator("privacy_key_pepper")
    @classmethod
    def _validate_pepper_length(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < MIN_SECRET_LENGTH:
            raise ValueError(f"PRIVACY_KEY_PEPPER must be at least {MIN_SECRET_LENGTH} characters")
        return value

    @model_validator(mode="after")
    def _validate_deployed_security(self) -> Settings:
        if self.service_env not in {"staging", "production"}:
            return self

        if self.jwt_algorithm.startswith("HS"):
            raise ValueError("Staging and production require asymmetric JWT algorithm (RS*/ES*)")
        if not self.cors_allowed_origins:
            raise ValueError("Staging and production require explicit CORS_ALLOWED_ORIGINS")
        if any(origin == "*" for origin in self.cors_allowed_origins):
            raise ValueError("Wildcard CORS origin is not allowed in staging or production")
        if "BEGIN" not in self.jwt_public_key_value:
            raise ValueError("Deployed asymmetric JWT public key must be PEM-formatted")
        return self

    @property
    def jwt_public_key_value(self) -> str:
        return self.jwt_public_key.get_secret_value()

    @property
    def privacy_key_pepper_value(self) -> str:
        return self.privacy_key_pepper.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
