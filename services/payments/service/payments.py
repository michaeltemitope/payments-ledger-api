from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from services.payments.domain.payments import (
    Money,
    Payment,
    PaymentNotFound,
    StorageUnavailable,
)
from services.payments.infra.models import PaymentRow


def utc_now() -> datetime:
    return datetime.now(UTC)


class PaymentService:
    def __init__(
        self, session: Session, clock: Callable[[], datetime] = utc_now
    ) -> None:
        self.session = session
        self.clock = clock

    def create(self, money: Money) -> Payment:
        now = self.clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Clock must return a timezone-aware datetime")
        payment = Payment(
            uuid4(), money.amount, money.currency, "created", now.astimezone(UTC)
        )
        try:
            with self.session.begin():
                self.session.add(
                    PaymentRow(
                        id=payment.id,
                        amount=payment.amount,
                        currency=payment.currency,
                        status=payment.status,
                        created_at=payment.created_at,
                    )
                )
        except SQLAlchemyError as error:
            raise StorageUnavailable("Payment storage is unavailable") from error
        return payment

    def get(self, payment_id: UUID) -> Payment:
        try:
            with self.session.begin():
                row = self.session.get(PaymentRow, payment_id)
                if row is None:
                    raise PaymentNotFound("Payment not found")
                return Payment(
                    row.id, row.amount, row.currency, row.status, row.created_at
                )
        except SQLAlchemyError as error:
            raise StorageUnavailable("Payment storage is unavailable") from error
