import pytest


@pytest.fixture(autouse=True)
def service_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    # Parsing configuration and constructing clients must never contact services.
    monkeypatch.setenv(
        "PAYMENTS_DATABASE_URL", "postgresql+psycopg://unit:unit@127.0.0.1:1/unit_test"
    )
    monkeypatch.setenv("PAYMENTS_REDIS_URL", "redis://127.0.0.1:1/0")
