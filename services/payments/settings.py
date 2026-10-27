from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PAYMENTS_", env_file=None)

    environment: Literal["development", "test", "production"]
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    listen_host: str = "127.0.0.1"
    database_url: SecretStr
    redis_url: SecretStr
    database_timeout_seconds: int = Field(default=3, ge=1, le=30)
    redis_timeout_seconds: float = Field(default=1, gt=0, le=30)
    database_pool_size: int = Field(default=5, ge=1, le=20)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            valid = url.drivername == "postgresql+psycopg" and bool(url.database)
        except (ValueError, ArgumentError):
            valid = False
        if not valid:
            raise ValueError("use a postgresql+psycopg URL with a database name")
        return value

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = urlsplit(value.get_secret_value())
            valid = url.scheme in {"redis", "rediss"} and bool(url.hostname)
            valid = valid and (url.port is None or url.port > 0)
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("use a redis or rediss URL with a hostname")
        return value
