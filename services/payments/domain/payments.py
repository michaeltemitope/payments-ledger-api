from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from services.payments.domain.currencies import ISO_4217_CODES

MAX_AMOUNT = 2**63 - 1


class PaymentError(Exception):
    pass


class InvalidMoney(PaymentError):
    pass


class PaymentNotFound(PaymentError):
    pass


class StorageUnavailable(PaymentError):
    pass


@dataclass(frozen=True)
class Money:
    amount: int
    currency: str

    def __post_init__(self) -> None:
        if type(self.amount) is not int or not 0 < self.amount <= MAX_AMOUNT:
            raise InvalidMoney("Amount must be a positive 64-bit integer")
        if self.currency not in ISO_4217_CODES:
            raise InvalidMoney("Currency must be an uppercase ISO 4217 code")


@dataclass(frozen=True)
class Payment:
    id: UUID
    amount: int
    currency: str
    status: str
    created_at: datetime
