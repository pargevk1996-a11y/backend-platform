from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Self

from cryptography.fernet import Fernet
from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
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

# Repo root: services/auth-service/app/core/config.py → parents[4] == backend-platform
_SETTINGS_FILE = Path(__file__).resolve()
_REPO_ROOT = _SETTINGS_FILE.parents[4]
_DEFAULT_SMTP_PASSWORD_FILE = _REPO_ROOT / "secrets" / "smtp_password.txt"
_SMTP_IDENTITY_FILE = _REPO_ROOT / "secrets" / "smtp_identity_email.txt"


def _normalize_smtp_secret(raw: str) -> str:
    """Strip and remove whitespace (Gmail app passwords are 16 chars without spaces)."""
    s = raw.strip()
    if not s:
        return ""
    return "".join(s.split())


def _normalize_smtp_identity_line(raw: str) -> str:
    line = raw.strip().splitlines()[0] if raw.strip() else ""
    return line.strip()


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
    rate_limit_revoke_per_minute: int = 30
    rate_limit_register_per_minute: int = 5
    rate_limit_password_reset_per_minute: int = 5

    brute_force_login_max_attempts: int = Field(
        default=3,
        validation_alias=AliasChoices(
            "BRUTE_FORCE_LOGIN_MAX_ATTEMPTS",
            "LOGIN_MAX_FAILED_ATTEMPTS",
            "brute_force_login_max_attempts",
        ),
    )
    brute_force_login_window_seconds: int = 300
    brute_force_login_lock_seconds: int = 900

    brute_force_2fa_max_attempts: int = 5
    brute_force_2fa_window_seconds: int = 300
    brute_force_2fa_lock_seconds: int = 900

    brute_force_password_reset_max_attempts: int = Field(
        default=3,
        validation_alias=AliasChoices(
            "BRUTE_FORCE_PASSWORD_RESET_MAX_ATTEMPTS",
            "RESET_CODE_MAX_FAILED_ATTEMPTS",
            "brute_force_password_reset_max_attempts",
        ),
    )
    brute_force_password_reset_window_seconds: int = 300
    brute_force_password_reset_lock_seconds: int = 900

    smtp_host: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_HOST", "smtp_host"),
    )
    smtp_port: int = Field(
        default=587,
        validation_alias=AliasChoices("SMTP_PORT", "smtp_port"),
    )
    smtp_username: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_USERNAME", "smtp_username"),
    )
    smtp_password: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_PASSWORD", "smtp_password"),
    )
    smtp_password_file: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_PASSWORD_FILE", "smtp_password_file"),
    )
    smtp_require_delivery: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_REQUIRE_DELIVERY", "smtp_require_delivery"),
    )
    smtp_use_tls: bool = Field(
        default=True,
        validation_alias=AliasChoices("SMTP_USE_TLS", "smtp_use_tls"),
    )
    smtp_from_email: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_FROM_EMAIL", "smtp_from_email"),
    )
    smtp_from_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_FROM_NAME", "smtp_from_name"),
    )
    auth_allow_missing_smtp: bool = Field(
        default=False,
        validation_alias=AliasChoices("AUTH_ALLOW_MISSING_SMTP", "auth_allow_missing_smtp"),
    )
    support_email: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SUPPORT_EMAIL", "support_email"),
    )

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

    @field_validator(
        "smtp_host",
        "smtp_username",
        "smtp_from_email",
        "smtp_from_name",
        "support_email",
        mode="before",
    )
    @classmethod
    def _blank_smtp_strings_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _load_smtp_password_from_file(self) -> Self:
        """When SMTP_PASSWORD is unset or blank, load it from file (env or default repo path)."""
        if self.smtp_password is not None:
            if _normalize_smtp_secret(self.smtp_password.get_secret_value()):
                return self

        raw_path = (self.smtp_password_file or "").strip()
        path = Path(raw_path) if raw_path else _DEFAULT_SMTP_PASSWORD_FILE
        if not path.is_file():
            return self

        raw = _normalize_smtp_secret(path.read_text(encoding="utf-8"))
        if not raw:
            return self

        self.smtp_password = SecretStr(raw)
        return self

    @model_validator(mode="after")
    def _apply_smtp_ec2_defaults(self) -> Self:
        """Fill host/mailbox from repo secrets when env is incomplete (typical on EC2)."""
        if _SMTP_IDENTITY_FILE.is_file():
            ident = _normalize_smtp_identity_line(_SMTP_IDENTITY_FILE.read_text(encoding="utf-8"))
            if ident and not self.smtp_username and not self.smtp_from_email:
                self.smtp_username = ident
                self.smtp_from_email = ident

        pw = ""
        if self.smtp_password is not None:
            pw = _normalize_smtp_secret(self.smtp_password.get_secret_value())
        if pw and not self.smtp_host:
            self.smtp_host = "smtp.gmail.com"
        return self

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
        if not self.smtp_is_configured and not self.auth_allow_missing_smtp:
            raise ValueError(
                "Staging and production require configured SMTP delivery "
                "(set AUTH_ALLOW_MISSING_SMTP=true when outbound email is intentionally disabled)"
            )

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

    @property
    def smtp_from_email_value(self) -> str | None:
        return self.smtp_from_email or self.smtp_username

    @property
    def smtp_password_value(self) -> str | None:
        if self.smtp_password is None:
            return None
        normalized = _normalize_smtp_secret(self.smtp_password.get_secret_value())
        return normalized or None

    @property
    def smtp_is_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from_email_value)

    @property
    def smtp_require_delivery_value(self) -> bool:
        if self.smtp_require_delivery is not None:
            return self.smtp_require_delivery
        smtp_partially_configured = any(
            [
                self.smtp_host,
                self.smtp_username,
                self.smtp_password,
                self.smtp_from_email,
            ]
        )
        return self.service_env != "development" or smtp_partially_configured

    @property
    def support_contact_sentence(self) -> str:
        if self.support_email:
            return f"If you need assistance, email {self.support_email}."
        return "If you need assistance, contact your platform administrator."

    @property
    def account_login_locked_message(self) -> str:
        return (
            "Too many failed sign-in attempts. Password sign-in is blocked for this account. "
            "Use password reset with your email to regain access. "
            + self.support_contact_sentence
        )

    @property
    def password_reset_flow_blocked_message(self) -> str:
        return (
            "Self-service password reset is not available for this account for security reasons. "
            + self.support_contact_sentence
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
