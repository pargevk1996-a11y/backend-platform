from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from cryptography.fernet import Fernet
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

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
MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Application settings loaded from service-specific .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "auth-service"
    service_env: Literal["development", "staging", "production"] = "development"
    service_port: int = 8001
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    trusted_proxy_ips: Annotated[list[str], NoDecode] = Field(default_factory=list)

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")

    jwt_algorithm: str = "RS256"
    jwt_issuer: str = "backend-platform"
    jwt_audience: str = "backend-clients"
    jwt_access_ttl_seconds: int = 900
    jwt_refresh_ttl_seconds: int = 60 * 60 * 24 * 30
    jwt_private_key: SecretStr = Field(alias="JWT_PRIVATE_KEY")
    jwt_public_key: SecretStr = Field(alias="JWT_PUBLIC_KEY")

    refresh_token_hash_pepper: SecretStr = Field(alias="REFRESH_TOKEN_HASH_PEPPER")
    privacy_key_pepper: SecretStr = Field(alias="PRIVACY_KEY_PEPPER")
    password_reset_token_pepper: SecretStr = Field(alias="PASSWORD_RESET_TOKEN_PEPPER")

    totp_issuer: str = "Backend Platform"
    totp_encryption_key: SecretStr = Field(alias="TOTP_ENCRYPTION_KEY")
    totp_code_digits: int = 6
    totp_interval_seconds: int = 30

    login_challenge_ttl_seconds: int = 300
    password_reset_token_ttl_seconds: int = 900

    rate_limit_login_per_minute: int = 10
    rate_limit_2fa_per_minute: int = 10
    rate_limit_2fa_setup_per_minute: int = 5
    rate_limit_refresh_per_minute: int = 30
    rate_limit_register_per_minute: int = 5
    rate_limit_password_reset_per_minute: int = 5

    brute_force_login_max_attempts: int = 5
    brute_force_login_window_seconds: int = 300
    brute_force_login_lock_seconds: int = 900

    brute_force_2fa_max_attempts: int = 5
    brute_force_2fa_window_seconds: int = 300
    brute_force_2fa_lock_seconds: int = 900

    brute_force_password_reset_max_attempts: int = 5
    brute_force_password_reset_window_seconds: int = 300
    brute_force_password_reset_lock_seconds: int = 900

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    smtp_from_email: str | None = None

    access_cookie_name: str = "access_token"
    refresh_cookie_name: str = "refresh_token"
    csrf_cookie_name: str = "csrf_token"
    cookie_secure: bool = True
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_domain: str | None = None

    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536
    argon2_parallelism: int = 4
    argon2_hash_length: int = 32
    argon2_salt_length: int = 16

    health_timeout_seconds: int = 2

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _parse_origins(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
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

    @field_validator(
        "refresh_token_hash_pepper", "privacy_key_pepper", "password_reset_token_pepper"
    )
    @classmethod
    def _validate_pepper_length(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < MIN_SECRET_LENGTH:
            raise ValueError(f"Pepper must be at least {MIN_SECRET_LENGTH} characters")
        return value

    @field_validator("totp_encryption_key")
    @classmethod
    def _validate_totp_key(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value().encode("utf-8")
        try:
            Fernet(raw)
        except Exception as exc:
            raise ValueError("TOTP_ENCRYPTION_KEY must be a valid Fernet key") from exc
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

        private_key = self.jwt_private_key_value
        public_key = self.jwt_public_key_value
        if "BEGIN" not in private_key or "BEGIN" not in public_key:
            raise ValueError("Deployed asymmetric JWT keys must be PEM-formatted")

        if not self.cookie_secure:
            raise ValueError("Staging and production require COOKIE_SECURE=true")
        if self.cookie_samesite == "none":
            raise ValueError("Staging and production forbid SameSite=None for auth cookies")
        return self

    @property
    def jwt_private_key_value(self) -> str:
        return self.jwt_private_key.get_secret_value()

    @property
    def jwt_public_key_value(self) -> str:
        return self.jwt_public_key.get_secret_value()

    @property
    def refresh_token_hash_pepper_value(self) -> str:
        return self.refresh_token_hash_pepper.get_secret_value()

    @property
    def privacy_key_pepper_value(self) -> str:
        return self.privacy_key_pepper.get_secret_value()

    @property
    def password_reset_token_pepper_value(self) -> str:
        return self.password_reset_token_pepper.get_secret_value()

    @property
    def password_reset_token_ttl_value(self) -> int:
        return max(60, self.password_reset_token_ttl_seconds)

    @property
    def totp_encryption_key_value(self) -> str:
        return self.totp_encryption_key.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
