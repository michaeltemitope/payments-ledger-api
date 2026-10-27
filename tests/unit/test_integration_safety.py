import pytest

from tests.integration.conftest import integration_settings


@pytest.mark.parametrize(
    "database_url",
    [None, "postgresql+psycopg://user:password@localhost/payments"],
)
def test_integration_setup_rejects_missing_or_unsafe_database(
    monkeypatch: pytest.MonkeyPatch,
    database_url: str | None,
) -> None:
    monkeypatch.delenv("PAYMENTS_TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv("PAYMENTS_TEST_REDIS_URL", "redis://127.0.0.1:1/0")
    if database_url is not None:
        monkeypatch.setenv("PAYMENTS_TEST_DATABASE_URL", database_url)
    with pytest.raises(pytest.fail.Exception):
        integration_settings()


def test_integration_setup_rejects_application_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "postgresql+psycopg://user:password@localhost/payments_test"
    monkeypatch.setenv("PAYMENTS_DATABASE_URL", url)
    monkeypatch.setenv("PAYMENTS_TEST_DATABASE_URL", url)
    monkeypatch.setenv("PAYMENTS_TEST_REDIS_URL", "redis://127.0.0.1:1/0")
    with pytest.raises(pytest.fail.Exception, match="must differ"):
        integration_settings()
