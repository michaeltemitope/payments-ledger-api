from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, func, insert, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.payments.infra.models import (
    Base,
    IdempotencyKeyRow,
    LedgerEntryRow,
    PaymentRow,
)
from tests.integration.conftest import migrate


def test_migration_matches_models(engine: Engine) -> None:
    with engine.connect() as connection:
        assert (
            compare_metadata(MigrationContext.configure(connection), Base.metadata)
            == []
        )
    assert {"payments", "idempotency_keys", "ledger_entries"} <= set(
        inspect(engine).get_table_names()
    )


def test_migration_can_be_reversed_and_reapplied(engine: Engine) -> None:
    try:
        migrate(engine, "base", downgrade=True)
        assert not {"payments", "idempotency_keys", "ledger_entries"} & set(
            inspect(engine).get_table_names()
        )
    finally:
        migrate(engine, "head")
    with engine.connect() as connection:
        assert (
            compare_metadata(MigrationContext.configure(connection), Base.metadata)
            == []
        )


@pytest.mark.parametrize("amount", [0, -1])
def test_database_rejects_nonpositive_amounts(engine: Engine, amount: int) -> None:
    with Session(engine) as session, pytest.raises(IntegrityError), session.begin():
        session.add(
            PaymentRow(
                id=uuid4(),
                amount=amount,
                currency="USD",
                status="created",
                created_at=datetime.now(UTC),
            )
        )


@pytest.mark.parametrize("amount", [0, -1])
def test_database_rejects_nonpositive_ledger_amounts(
    engine: Engine, amount: int
) -> None:
    payment_id = uuid4()
    now = datetime.now(UTC)
    with Session(engine) as session:
        session.add(
            PaymentRow(
                id=payment_id,
                amount=100,
                currency="USD",
                status="created",
                created_at=now,
            )
        )
        session.flush()
        session.add(
            LedgerEntryRow(
                id=uuid4(),
                payment_id=payment_id,
                account="reserved",
                direction="debit",
                amount=amount,
                currency="USD",
                created_at=now,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
    # A constraint failure rolls back the whole transaction, including the payment.
    with Session(engine) as session:
        assert session.get(PaymentRow, payment_id) is None


def test_reserved_idempotency_schema_enforces_unique_key(engine: Engine) -> None:
    payment_id = uuid4()
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            insert(PaymentRow).values(
                id=payment_id,
                amount=100,
                currency="USD",
                status="created",
                created_at=now,
            )
        )
        connection.execute(
            insert(IdempotencyKeyRow).values(
                id=uuid4(),
                key="reserved-key",
                request_hash="a" * 64,
                payment_id=payment_id,
                response_status=201,
                response_body={},
                created_at=now,
            )
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            insert(IdempotencyKeyRow).values(
                id=uuid4(),
                key="reserved-key",
                request_hash="a" * 64,
                payment_id=payment_id,
                response_status=201,
                response_body={},
                created_at=now,
            )
        )
    with engine.connect() as connection:
        assert (
            connection.scalar(select(func.count()).select_from(IdempotencyKeyRow)) == 1
        )


def test_reserved_ledger_schema_enforces_payment_reference(engine: Engine) -> None:
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            insert(LedgerEntryRow).values(
                id=uuid4(),
                payment_id=uuid4(),
                account="reserved",
                direction="debit",
                amount=100,
                currency="USD",
                created_at=datetime.now(UTC),
            )
        )
