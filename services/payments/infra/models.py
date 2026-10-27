from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PaymentRow(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_payments_currency"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(Text, server_default=text("'created'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IdempotencyKeyRow(Base):
    __tablename__ = "idempotency_keys"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(255), unique=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    payment_id: Mapped[UUID] = mapped_column(ForeignKey("payments.id"), index=True)
    response_status: Mapped[int] = mapped_column(SmallInteger)
    response_body: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LedgerEntryRow(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_ledger_entries_amount_positive"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_ledger_entries_currency"),
        CheckConstraint("direction IN ('debit', 'credit')", name="ck_ledger_direction"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    payment_id: Mapped[UUID] = mapped_column(ForeignKey("payments.id"), index=True)
    account: Mapped[str] = mapped_column(Text)
    direction: Mapped[str] = mapped_column(Text)
    amount: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
