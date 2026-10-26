import json
import subprocess
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from io import StringIO

from services.payments.logging import JsonFormatter, create_logger


def test_logs_are_json_with_utc_timestamp_and_request_id() -> None:
    request_id: ContextVar[str | None] = ContextVar("test_request_id", default=None)
    stream = StringIO()
    logger = create_logger("INFO", request_id, stream)
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    logger.handlers[0].setFormatter(JsonFormatter(request_id, lambda: timestamp))
    token = request_id.set("caller-123")
    try:
        logger.info("hello %s\nworld", "payments")
    finally:
        request_id.reset(token)

    assert len(stream.getvalue().splitlines()) == 1
    assert json.loads(stream.getvalue()) == {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "level": "INFO",
        "logger": "payments",
        "message": "hello payments\nworld",
        "request_id": "caller-123",
    }


def test_logs_outside_a_request_have_null_request_id() -> None:
    request_id: ContextVar[str | None] = ContextVar("test_request_id", default=None)
    stream = StringIO()
    create_logger("INFO", request_id, stream).info("startup")

    assert json.loads(stream.getvalue())["request_id"] is None


def test_configured_level_filters_lower_severity_messages() -> None:
    request_id: ContextVar[str | None] = ContextVar("test_request_id", default=None)
    stream = StringIO()
    logger = create_logger("WARNING", request_id, stream)

    logger.info("hidden")
    logger.warning("visible")

    assert len(stream.getvalue().splitlines()) == 1
    assert json.loads(stream.getvalue())["message"] == "visible"


def test_app_loggers_do_not_share_handlers_or_levels() -> None:
    request_id: ContextVar[str | None] = ContextVar("test_request_id", default=None)
    first_stream, second_stream = StringIO(), StringIO()
    first = create_logger("INFO", request_id, first_stream)
    second = create_logger("ERROR", request_id, second_stream)

    first.info("first")
    second.info("hidden")
    second.error("second")

    assert json.loads(first_stream.getvalue())["message"] == "first"
    assert json.loads(second_stream.getvalue())["message"] == "second"
    assert first.handlers[0] is not second.handlers[0]


def test_formatter_does_not_serialize_arbitrary_extra_fields() -> None:
    request_id: ContextVar[str | None] = ContextVar("test_request_id", default=None)
    stream = StringIO()
    create_logger("INFO", request_id, stream).info(
        "event", extra={"authorization": "secret", "status_code": 200}
    )

    assert "secret" not in stream.getvalue()
    assert json.loads(stream.getvalue())["status_code"] == 200


def test_server_and_library_logs_use_json_with_request_context() -> None:
    # Run in isolation because server startup intentionally configures root logging.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from contextvars import ContextVar\n"
            "import logging, logging.config\n"
            "from services.payments.logging import create_server_log_config\n"
            "context = ContextVar('request_id', default=None)\n"
            "logging.config.dictConfig(create_server_log_config('INFO', context))\n"
            "logging.getLogger('uvicorn.error').info('startup')\n"
            "context.set('library-request')\n"
            "logging.getLogger('library').info('inside')\n",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )

    records = [json.loads(line) for line in result.stderr.splitlines()]
    assert len(records) == 2
    assert records[0]["logger"] == "uvicorn.error"
    assert records[0]["request_id"] is None
    assert records[1]["logger"] == "library"
    assert records[1]["request_id"] == "library-request"
