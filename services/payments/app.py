from contextvars import ContextVar

from fastapi import FastAPI

from services.payments.api.health import create_health_router
from services.payments.logging import create_logger
from services.payments.middleware import RequestLoggingMiddleware
from services.payments.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings if settings is not None else Settings()
    app = FastAPI(title="Payments Ledger API", version="0.1.0")
    app.state.settings = resolved_settings
    request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
    logger = create_logger(resolved_settings.log_level, request_id)
    app.state.logger = logger
    app.state.request_id_context = request_id
    app.add_middleware(RequestLoggingMiddleware, logger=logger, request_id=request_id)
    app.include_router(create_health_router())
    return app
