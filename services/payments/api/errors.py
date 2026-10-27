from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services.payments.domain.payments import (
    InvalidMoney,
    PaymentError,
    PaymentNotFound,
    StorageUnavailable,
)


class ErrorResponse(BaseModel):
    detail: str


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(PaymentError, payment_error_response)


async def payment_error_response(request: Request, error: Exception) -> JSONResponse:
    if isinstance(error, PaymentNotFound):
        status, detail = 404, "Payment not found"
    elif isinstance(error, InvalidMoney):
        status, detail = 422, str(error)
    elif isinstance(error, StorageUnavailable):
        status, detail = 503, "Payment storage is unavailable"
        request.app.state.logger.warning("payment_storage_unavailable")
    else:
        status, detail = 500, "Internal server error"
    return JSONResponse(status_code=status, content={"detail": detail})
