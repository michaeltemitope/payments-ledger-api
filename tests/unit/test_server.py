from typing import Any

import pytest
from fastapi import FastAPI

from services.payments.__main__ import main


def test_server_uses_json_logging_and_middleware_access_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAYMENTS_ENVIRONMENT", "test")
    monkeypatch.setenv("PAYMENTS_LOG_LEVEL", "WARNING")
    calls: list[dict[str, Any]] = []

    def capture_run(app: FastAPI, **kwargs: Any) -> None:
        calls.append({"app": app, **kwargs})

    monkeypatch.setattr("uvicorn.run", capture_run)

    main()

    assert len(calls) == 1
    assert calls[0]["access_log"] is False
    config = calls[0]["log_config"]
    assert config["root"]["level"] == "WARNING"
    assert config["formatters"]["json"]["request_id"] is (
        calls[0]["app"].state.request_id_context
    )
