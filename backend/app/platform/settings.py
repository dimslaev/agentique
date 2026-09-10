"""Application settings loaded from environment variables."""

from __future__ import annotations

import secrets
import warnings
from typing import Annotated, Literal, Self
from urllib.parse import quote, urlencode

from pydantic import (
    AnyUrl,
    BeforeValidator,
    EmailStr,
    HttpUrl,
    PostgresDsn,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v: list[str] | str) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):  # type: ignore[explicit-any]  # BaseSettings itself is the Any source, not this file
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    FRONTEND_HOST: str = "http://localhost:5173"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return PostgresDsn.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    # The MCP server (app/mcp/) is gated by this one shared bearer token. Unset
    # means every request is rejected, so a deploy that forgets it is closed,
    # not open.
    MCP_TOKEN: str | None = None
    # The MCP `sql_query` tool logs in as its own role, not as POSTGRES_USER.
    MCP_DB_USER: str = "agentique_ro"
    MCP_DB_PASSWORD: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def MCP_DATABASE_URI(self) -> str:
        """Read-only DSN for the MCP `sql_query` tool.

        The role's SELECT-only grants are the boundary. The read-only flag
        set here is a seatbelt, not a lock: `default_transaction_read_only` is
        USERSET, so the session can turn it back off -- it catches a mistaken
        write at the first statement, it does not contain a determined one.
        The statement timeout is tighter than the role's own (30s) so a
        runaway query cannot hold a backend worker for long.
        """
        dsn = PostgresDsn.build(
            scheme="postgresql",
            username=self.MCP_DB_USER,
            password=self.MCP_DB_PASSWORD or None,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )
        # quote, not the default quote_plus: libpq percent-decodes a URI query
        # and leaves `+` as a literal plus, so spaces have to be %20.
        options = urlencode(
            {"options": "-c default_transaction_read_only=on -c statement_timeout=10s"},
            quote_via=quote,
        )
        return f"{dsn}?{options}"

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    RESEND_API_KEY: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.EMAILS_FROM_EMAIL and (self.RESEND_API_KEY or self.SMTP_HOST))

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "development":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._check_default_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )

        return self


settings = Settings()  # type: ignore
