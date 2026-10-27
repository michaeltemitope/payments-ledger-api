import pytest
from pydantic import ValidationError

from services.payments.api.payments import CreatePaymentRequest
from services.payments.domain.payments import MAX_AMOUNT, InvalidMoney, Money


@pytest.mark.parametrize("amount", [1, MAX_AMOUNT])
def test_accepts_positive_integer_minor_units(amount: int) -> None:
    assert Money(amount, "USD").amount == amount
    assert CreatePaymentRequest(amount=amount, currency="USD").amount == amount


@pytest.mark.parametrize("amount", [0, -1, MAX_AMOUNT + 1, True, 1.0, "1", None])
def test_rejects_non_integer_or_out_of_range_amounts(amount: object) -> None:
    with pytest.raises(ValidationError):
        CreatePaymentRequest.model_validate({"amount": amount, "currency": "USD"})
    with pytest.raises(InvalidMoney):
        Money(amount, "USD")  # type: ignore[arg-type]


@pytest.mark.parametrize("currency", ["USD", "EUR", "JPY", "GBP"])
def test_accepts_iso_currency(currency: str) -> None:
    assert Money(100, currency).currency == currency


@pytest.mark.parametrize("currency", ["usd", "ZZZ", "US", "USDD", " USD", ""])
def test_rejects_invalid_currency(currency: str) -> None:
    with pytest.raises(InvalidMoney):
        Money(100, currency)
    with pytest.raises(ValidationError):
        CreatePaymentRequest(amount=100, currency=currency)
