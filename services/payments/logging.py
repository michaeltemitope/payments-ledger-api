import json
import logging
from collections.abc import Callable
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import TextIO


def utc_now() -> datetime:
    return datetime.now(UTC)


class JsonFormatter(logging.Formatter):
    def __init__(
        self,
        request_id: ContextVar[str | None],
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        super().__init__()
        self.request_id = request_id
        self.clock = clock

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.clock().astimezone(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": self.request_id.get(),
        }
        for field in ("method", "status_code", "exception_type"):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        return json.dumps(payload, ensure_ascii=True)


def create_logger(
    level: str, request_id: ContextVar[str | None], stream: TextIO | None = None
) -> logging.Logger:
    # Each app owns its logger so factories do not accumulate global handlers.
    logger = logging.Logger("payments", level=level)
    logger.propagate = False
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter(request_id))
    logger.addHandler(handler)
    return logger


def create_server_log_config(
    level: str, request_id: ContextVar[str | None]
) -> dict[str, object]:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"json": {"()": JsonFormatter, "request_id": request_id}},
        "handlers": {
            "json": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": "ext://sys.stderr",
            }
        },
        "root": {"handlers": ["json"], "level": level},
        "loggers": {
            name: {"handlers": [], "propagate": True, "level": level}
            for name in ("uvicorn", "uvicorn.error", "uvicorn.access")
        },
    }
