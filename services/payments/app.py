from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar

from fastapi import FastAPI
from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from services.payments.api.errors import register_error_handlers
from services.payments.api.health import create_health_router
from services.payments.api.payments import create_payments_router
from services.payments.infra.database import create_database_engine
from services.payments.logging import create_logger
from services.payments.middleware import RequestLoggingMiddleware
from services.payments.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings if settings is not None else Settings()
    engine = create_database_engine(resolved_settings)
    redis_client = Redis.from_url(
        resolved_settings.redis_url.get_secret_value(),
        socket_connect_timeout=resolved_settings.redis_timeout_seconds,
        socket_timeout=resolved_settings.redis_timeout_seconds,
        retry=Retry(NoBackoff(), 0),
        max_connections=resolved_settings.database_pool_size,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            redis_client.close()
            engine.dispose()

    app = FastAPI(title="Payments Ledger API", version="0.1.0", lifespan=lifespan)
    app.state.engine = engine
    app.state.redis_client = redis_client
    app.state.settings = resolved_settings
    request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
    logger = create_logger(resolved_settings.log_level, request_id)
    app.state.logger = logger
    app.state.request_id_context = request_id
    app.add_middleware(RequestLoggingMiddleware, logger=logger, request_id=request_id)
    app.include_router(create_health_router())
    app.include_router(create_payments_router())
    register_error_handlers(app)
    return app
