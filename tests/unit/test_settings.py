from pathlib import Path

import pytest
from pydantic import ValidationError

from services.payments.settings import Settings


@pytest.fixture(autouse=True)
def clear_settings_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PAYMENTS_ENVIRONMENT", raising=False)
    monkeypatch.delenv("PAYMENTS_LOG_LEVEL", raising=False)


@pytest.mark.parametrize("environment", ["development", "test", "production"])
def test_reads_environment_configuration(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setenv("PAYMENTS_ENVIRONMENT", environment)

    assert Settings().environment == environment


def test_defaults_log_level_to_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAYMENTS_ENVIRONMENT", "test")

    assert Settings().log_level == "INFO"


@pytest.mark.parametrize("log_level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
def test_reads_log_level_configuration(
    monkeypatch: pytest.MonkeyPatch, log_level: str
) -> None:
    monkeypatch.setenv("PAYMENTS_ENVIRONMENT", "test")
    monkeypatch.setenv("PAYMENTS_LOG_LEVEL", log_level)

    assert Settings().log_level == log_level


def test_missing_environment_fails_immediately() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert exc_info.value.errors()[0]["loc"] == ("environment",)
    assert exc_info.value.errors()[0]["type"] == "missing"


@pytest.mark.parametrize("environment", ["", "staging", "TEST", " test "])
def test_rejects_invalid_environment(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setenv("PAYMENTS_ENVIRONMENT", environment)

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert exc_info.value.errors()[0]["loc"] == ("environment",)
    assert exc_info.value.errors()[0]["type"] == "literal_error"


@pytest.mark.parametrize("log_level", ["", "TRACE", "info", " INFO "])
def test_rejects_invalid_log_level(
    monkeypatch: pytest.MonkeyPatch, log_level: str
) -> None:
    monkeypatch.setenv("PAYMENTS_ENVIRONMENT", "test")
    monkeypatch.setenv("PAYMENTS_LOG_LEVEL", log_level)

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert exc_info.value.errors()[0]["loc"] == ("log_level",)
    assert exc_info.value.errors()[0]["type"] == "literal_error"


def test_instances_read_configuration_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAYMENTS_ENVIRONMENT", "development")
    monkeypatch.setenv("PAYMENTS_LOG_LEVEL", "DEBUG")
    first = Settings()

    monkeypatch.setenv("PAYMENTS_ENVIRONMENT", "production")
    monkeypatch.setenv("PAYMENTS_LOG_LEVEL", "ERROR")
    second = Settings()

    assert (first.environment, first.log_level) == ("development", "DEBUG")
    assert (second.environment, second.log_level) == ("production", "ERROR")


def test_does_not_automatically_load_dotenv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "PAYMENTS_ENVIRONMENT=development\n", encoding="utf-8"
    )

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert exc_info.value.errors()[0]["type"] == "missing"


@pytest.mark.parametrize("field", ["DATABASE_URL", "REDIS_URL"])
def test_service_urls_are_required(monkeypatch: pytest.MonkeyPatch, field: str) -> None:
    monkeypatch.setenv("PAYMENTS_ENVIRONMENT", "test")
    monkeypatch.delenv(f"PAYMENTS_{field}")
    with pytest.raises(ValidationError) as error:
        Settings()
    assert error.value.errors()[0]["loc"] == (field.lower(),)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("DATABASE_URL", "sqlite:///test.db"),
        ("DATABASE_URL", "not-a-url"),
        ("DATABASE_URL", "postgresql+psycopg://localhost"),
        ("REDIS_URL", "http://localhost"),
        ("REDIS_URL", "redis://localhost:invalid"),
        ("DATABASE_TIMEOUT_SECONDS", "0"),
        ("REDIS_TIMEOUT_SECONDS", "0"),
        ("DATABASE_POOL_SIZE", "0"),
    ],
)
def test_invalid_service_configuration_fails_fast(
    monkeypatch: pytest.MonkeyPatch, field: str, value: str
) -> None:
    monkeypatch.setenv("PAYMENTS_ENVIRONMENT", "test")
    monkeypatch.setenv(f"PAYMENTS_{field}", value)
    with pytest.raises(ValidationError):
        Settings()


def test_settings_representation_does_not_expose_credentials() -> None:
    settings = Settings(environment="test")
    assert "unit:unit" not in repr(settings)
    assert settings.database_url.get_secret_value().endswith("/unit_test")
