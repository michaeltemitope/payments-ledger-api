import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, delete
from sqlalchemy.engine import make_url

from services.payments.app import create_app
from services.payments.infra.database import create_database_engine
from services.payments.infra.models import IdempotencyKeyRow, LedgerEntryRow, PaymentRow
from services.payments.settings import Settings


def integration_settings() -> Settings:
    database_url = os.environ.get("PAYMENTS_TEST_DATABASE_URL")
    redis_url = os.environ.get("PAYMENTS_TEST_REDIS_URL")
    if not database_url or not redis_url:
        pytest.fail(
            "Set PAYMENTS_TEST_DATABASE_URL and PAYMENTS_TEST_REDIS_URL; "
            "services must be running"
        )
    test_url = make_url(database_url)
    app_url = os.environ.get("PAYMENTS_DATABASE_URL")
    if not test_url.database or not test_url.database.endswith("_test"):
        pytest.fail("Integration database name must end in _test")
    if app_url and make_url(app_url).database == test_url.database:
        pytest.fail("Integration database must differ from the application database")
    return Settings(
        environment="test",
        database_url=SecretStr(database_url),
        redis_url=SecretStr(redis_url),
    )


def migrate(engine: Engine, revision: str, *, downgrade: bool = False) -> None:
    config = Config("alembic.ini")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        if downgrade:
            command.downgrade(config, revision)
        else:
            command.upgrade(config, revision)


@pytest.fixture(scope="session")
def settings() -> Settings:
    return integration_settings()


@pytest.fixture(scope="session")
def engine(settings: Settings) -> Iterator[Engine]:
    database = create_database_engine(settings)
    try:
        migrate(database, "head")
        yield database
    finally:
        database.dispose()


@pytest.fixture(autouse=True)
def clean_payments(engine: Engine) -> Iterator[None]:
    def clean() -> None:
        with engine.begin() as connection:
            connection.execute(delete(LedgerEntryRow))
            connection.execute(delete(IdempotencyKeyRow))
            connection.execute(delete(PaymentRow))

    clean()
    yield
    clean()


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
