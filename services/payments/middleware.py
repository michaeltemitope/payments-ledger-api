import logging
import re
from contextvars import ContextVar
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


def resolve_request_id(scope: Scope) -> str:
    values: list[bytes] = [
        value
        for name, value in scope.get("headers", [])
        if name.lower() == b"x-request-id"
    ]
    if len(values) == 1 and re.fullmatch(rb"[A-Za-z0-9._-]{1,128}", values[0]):
        return values[0].decode("ascii")
    return str(uuid4())


class RequestLoggingMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        logger: logging.Logger,
        request_id: ContextVar[str | None],
    ) -> None:
        self.app = app
        self.logger = logger
        self.request_id = request_id

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        current_id = resolve_request_id(scope)
        token = self.request_id.set(current_id)
        scope.setdefault("state", {})["request_id"] = current_id
        status_code: int | None = None

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = current_id
            await send(message)

        try:
            try:
                await self.app(scope, receive, send_with_request_id)
            except Exception as exc:
                self.logger.error(
                    "request_failed",
                    extra={
                        "method": scope["method"],
                        "exception_type": type(exc).__name__,
                    },
                )
                if status_code is None:
                    response = PlainTextResponse(
                        "Internal Server Error", status_code=500
                    )
                    await response(scope, receive, send_with_request_id)
                # Preserve ASGI error reporting even after headers were sent.
                raise
            finally:
                if status_code is not None:
                    self.logger.info(
                        "request_completed",
                        extra={"method": scope["method"], "status_code": status_code},
                    )
        finally:
            self.request_id.reset(token)
