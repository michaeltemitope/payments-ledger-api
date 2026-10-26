from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from services.payments.domain.payments import Money
from services.payments.infra.models import IdempotencyKeyRow, LedgerEntryRow, PaymentRow
from services.payments.service.payments import PaymentService


def test_create_payment_is_persisted_and_retrievable(
    client: TestClient, engine: Engine
) -> None:
    response = client.post(
        "/v1/payments",
        json={"amount": 1234, "currency": "USD"},
        headers={"X-Request-ID": "create-payment"},
    )
    assert response.status_code == 201
    payment = response.json()
    assert UUID(payment["id"]).version == 4
    assert payment["amount"] == 1234
    assert payment["currency"] == "USD"
    assert payment["status"] == "created"
    assert datetime.fromisoformat(payment["created_at"]).utcoffset() == UTC.utcoffset(
        None
    )
    assert response.headers["Location"] == f"/v1/payments/{payment['id']}"
    assert response.headers["X-Request-ID"] == "create-payment"
    fetched = client.get(response.headers["Location"])
    assert fetched.status_code == 200
    assert fetched.json() == payment
    # Independent session proves commit rather than an in-memory response.
    with Session(engine) as session:
        row = session.get(PaymentRow, UUID(payment["id"]))
        assert row is not None
        assert (row.amount, row.currency, row.status) == (1234, "USD", "created")


def test_unknown_payment_returns_404(client: TestClient) -> None:
    response = client.get(f"/v1/payments/{uuid4()}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Payment not found"}
    assert "X-Request-ID" in response.headers


def test_invalid_payment_id_returns_422(client: TestClient) -> None:
    assert client.get("/v1/payments/not-a-uuid").status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"amount": 0, "currency": "USD"},
        {"amount": -1, "currency": "USD"},
        {"amount": 1.0, "currency": "USD"},
        {"amount": True, "currency": "USD"},
        {"amount": "100", "currency": "USD"},
        {"amount": 2**63, "currency": "USD"},
        {"amount": 100, "currency": "usd"},
        {"amount": 100, "currency": "ZZZ"},
        {"amount": 100},
        {"amount": 100, "currency": "USD", "unexpected": "value"},
    ],
)
def test_invalid_payment_is_not_persisted(
    client: TestClient,
    engine: Engine,
    body: dict[str, object],
) -> None:
    response = client.post("/v1/payments", json=body)
    assert response.status_code == 422
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(PaymentRow)) == 0


def test_idempotency_header_is_not_enforced_yet(
    client: TestClient, engine: Engine
) -> None:
    body = {"amount": 100, "currency": "EUR"}
    first = client.post("/v1/payments", json=body, headers={"Idempotency-Key": "same"})
    second = client.post("/v1/payments", json=body, headers={"Idempotency-Key": "same"})
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(PaymentRow)) == 2
        assert session.scalar(select(func.count()).select_from(IdempotencyKeyRow)) == 0
        assert session.scalar(select(func.count()).select_from(LedgerEntryRow)) == 0


def test_service_uses_injected_utc_clock(engine: Engine) -> None:
    now = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)
    with Session(engine) as session:
        payment = PaymentService(session, clock=lambda: now).create(Money(500, "GBP"))
    with Session(engine) as session:
        stored = session.get(PaymentRow, payment.id)
        assert stored is not None
        assert stored.created_at == now


@pytest.mark.parametrize("amount", [1, 2**63 - 1])
def test_bigint_minor_unit_boundaries_round_trip(
    client: TestClient, amount: int
) -> None:
    response = client.post("/v1/payments", json={"amount": amount, "currency": "JPY"})
    assert response.status_code == 201
    assert response.json()["amount"] == amount
    fetched = client.get(response.headers["Location"])
    assert fetched.status_code == 200
    assert fetched.json()["amount"] == amount
