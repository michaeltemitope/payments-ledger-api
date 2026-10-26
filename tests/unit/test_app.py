import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from services.payments.api.dependencies import dependencies_ready
from services.payments.app import create_app
from services.payments.settings import Settings


@pytest.fixture(autouse=True)
def clear_settings_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PAYMENTS_ENVIRONMENT", raising=False)
    monkeypatch.delenv("PAYMENTS_LOG_LEVEL", raising=False)


@pytest.mark.parametrize(
    ("path", "expected_status"), [("/health", "ok"), ("/ready", "ready")]
)
def test_operational_endpoint_returns_status(path: str, expected_status: str) -> None:
    app = create_app(Settings(environment="test"))
    app.dependency_overrides[dependencies_ready] = lambda: True
    with TestClient(app) as client:
        response = client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"status": expected_status}


def test_factory_loads_settings_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAYMENTS_ENVIRONMENT", "production")
    monkeypatch.setenv("PAYMENTS_LOG_LEVEL", "ERROR")

    app = create_app()

    assert app.state.settings.environment == "production"
    assert app.state.settings.log_level == "ERROR"


def test_factory_accepts_explicit_settings_without_environment() -> None:
    settings = Settings(environment="test", log_level="DEBUG")

    app = create_app(settings)

    assert app.state.settings is settings


def test_factory_fails_immediately_when_configuration_is_missing() -> None:
    with pytest.raises(ValidationError) as exc_info:
        create_app()

    assert exc_info.value.errors()[0]["loc"] == ("environment",)
    assert exc_info.value.errors()[0]["type"] == "missing"


def test_factory_rejects_invalid_environment_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAYMENTS_ENVIRONMENT", "invalid")

    with pytest.raises(ValidationError) as exc_info:
        create_app()

    assert exc_info.value.errors()[0]["loc"] == ("environment",)


def test_factory_creates_independent_app_instances() -> None:
    first = create_app(Settings(environment="development"))
    second = create_app(Settings(environment="production"))
    first.state.settings.environment = "test"
    first.state.marker = "first-only"

    assert second.state.settings.environment == "production"
    assert not hasattr(second.state, "marker")


@pytest.mark.parametrize(
    ("path", "schema_name", "status"),
    [("/health", "HealthResponse", "ok"), ("/ready", "ReadyResponse", "ready")],
)
def test_openapi_describes_operational_response(
    path: str, schema_name: str, status: str
) -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    response_schema = schema["paths"][path]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert response_schema == {"$ref": f"#/components/schemas/{schema_name}"}
    model_schema = schema["components"]["schemas"][schema_name]
    assert model_schema["required"] == ["status"]
    assert model_schema["properties"]["status"]["const"] == status


@pytest.mark.parametrize("path", ["/v1/health", "/v1/ready"])
def test_operational_endpoints_are_only_unversioned(path: str) -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get(path)

    assert response.status_code == 404


@pytest.mark.parametrize("reachable", [True, False])
def test_readiness_reports_dependency_availability(reachable: bool) -> None:
    app = create_app(Settings(environment="test"))
    app.dependency_overrides[dependencies_ready] = lambda: reachable
    with TestClient(app) as client:
        response = client.get("/ready", headers={"X-Request-ID": "readiness"})
    assert response.status_code == (200 if reachable else 503)
    assert response.json() == {"status": "ready" if reachable else "not_ready"}
    assert response.headers["X-Request-ID"] == "readiness"
