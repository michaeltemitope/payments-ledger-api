from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from services.payments.app import create_app
from services.payments.settings import Settings


def test_ready_checks_real_postgres_and_redis(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@pytest.fixture
def unavailable_client(
    settings: Settings, request: pytest.FixtureRequest
) -> Iterator[TestClient]:
    field = str(request.param)
    unavailable = settings.model_copy(
        update={
            field: SecretStr(
                "postgresql+psycopg://unavailable:unavailable@127.0.0.1:1/unavailable_test"
                if field == "database_url"
                else "redis://127.0.0.1:1/0"
            )
        }
    )
    with TestClient(create_app(unavailable)) as client:
        yield client


@pytest.mark.parametrize(
    "unavailable_client", ["database_url", "redis_url"], indirect=True
)
def test_dependency_failure_makes_ready_unavailable_but_health_stays_live(
    unavailable_client: TestClient,
) -> None:
    response = unavailable_client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
    assert unavailable_client.get("/health").status_code == 200


@pytest.mark.parametrize("unavailable_client", ["database_url"], indirect=True)
def test_storage_failure_returns_safe_503(unavailable_client: TestClient) -> None:
    response = unavailable_client.post(
        "/v1/payments", json={"amount": 100, "currency": "USD"}
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "Payment storage is unavailable"}
    assert "unavailable:unavailable" not in response.text
    assert "X-Request-ID" in response.headers
