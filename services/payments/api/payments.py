from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from services.payments.api.dependencies import get_payment_service
from services.payments.api.errors import ErrorResponse
from services.payments.domain.currencies import ISO_4217_CODES
from services.payments.domain.payments import MAX_AMOUNT, Money
from services.payments.service.payments import PaymentService


class CreatePaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Annotated[StrictInt, Field(gt=0, le=MAX_AMOUNT)]
    currency: str = Field(
        pattern="^[A-Z]{3}$",
        json_schema_extra={"enum": [code for code in sorted(ISO_4217_CODES)]},
    )

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        if value not in ISO_4217_CODES:
            raise ValueError("Currency must be an ISO 4217 code")
        return value


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    amount: int
    currency: str
    status: Literal["created"]
    created_at: datetime


def create_payments_router() -> APIRouter:
    router = APIRouter(prefix="/v1/payments", tags=["payments"])
    router.add_api_route(
        "",
        create_payment,
        methods=["POST"],
        status_code=201,
        response_model=PaymentResponse,
        responses={
            201: {"headers": {"Location": {"schema": {"type": "string"}}}},
            503: {"model": ErrorResponse},
        },
    )
    router.add_api_route(
        "/{payment_id}",
        get_payment,
        methods=["GET"],
        response_model=PaymentResponse,
        responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )
    return router


def create_payment(
    body: CreatePaymentRequest,
    response: Response,
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentResponse:
    payment = service.create(Money(body.amount, body.currency))
    response.headers["Location"] = f"/v1/payments/{payment.id}"
    return PaymentResponse.model_validate(payment)


def get_payment(
    payment_id: UUID,
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentResponse:
    return PaymentResponse.model_validate(service.get(payment_id))
