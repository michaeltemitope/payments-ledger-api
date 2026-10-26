from contextvars import ContextVar
from typing import cast

import uvicorn

from services.payments.app import create_app
from services.payments.logging import create_server_log_config
from services.payments.settings import Settings


def main() -> None:
    app = create_app()
    settings = cast(Settings, app.state.settings)
    request_id = cast(ContextVar[str | None], app.state.request_id_context)
    # Middleware supplies access logs without Uvicorn's raw paths and query strings.
    uvicorn.run(
        app,
        log_config=create_server_log_config(settings.log_level, request_id),
        access_log=False,
    )


if __name__ == "__main__":
    main()
