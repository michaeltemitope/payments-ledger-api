from fastapi import FastAPI

from services.payments.api.health import create_health_router
from services.payments.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings if settings is not None else Settings()
    app = FastAPI(title="Payments Ledger API", version="0.1.0")
    app.state.settings = resolved_settings
    app.include_router(create_health_router())
    return app
