from sqlalchemy import Engine, create_engine

from services.payments.settings import Settings


def create_database_engine(settings: Settings) -> Engine:
    timeout = settings.database_timeout_seconds
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_size=settings.database_pool_size,
        max_overflow=0,
        pool_timeout=timeout,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={
            "connect_timeout": timeout,
            "options": (
                f"-c statement_timeout={timeout * 1000} "
                f"-c lock_timeout={timeout * 1000} "
                f"-c idle_in_transaction_session_timeout={timeout * 1000} "
                "-c timezone=UTC"
            ),
        },
    )
