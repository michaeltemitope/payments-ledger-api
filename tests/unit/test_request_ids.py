import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextvars import ContextVar
from io import StringIO
from typing import cast
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import StreamingResponse

from services.payments.app import create_app
from services.payments.settings import Settings


@pytest.fixture
def log_output() -> StringIO:
    return StringIO()


@pytest.fixture
def app(log_output: StringIO) -> FastAPI:
    application = create_app(Settings(environment="test", log_level="INFO"))
    logger = cast(logging.Logger, application.state.logger)
    handler = cast(logging.StreamHandler[StringIO], logger.handlers[0])
    handler.setStream(log_output)
    return application


@pytest.mark.parametrize("request_id", ["a", "abc-123_DEF.xyz", "a" * 128])
def test_supplied_request_id_is_returned_and_logged(
    app: FastAPI, log_output: StringIO, request_id: str
) -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": request_id})

    assert response.headers["X-Request-ID"] == request_id
    record = json.loads(log_output.getvalue())
    assert record["request_id"] == request_id
    assert record["message"] == "request_completed"
    assert record["status_code"] == 200


@pytest.mark.parametrize(
    "request_id", [None, "", "a" * 129, "a b", "bad\r\nid", "café"]
)
def test_missing_or_invalid_request_id_is_replaced_with_uuid(
    app: FastAPI, request_id: str | None
) -> None:
    headers = (
        [] if request_id is None else [(b"X-Request-ID", request_id.encode("latin1"))]
    )
    with TestClient(app) as client:
        response = client.get("/health", headers=headers)

    generated = response.headers["X-Request-ID"]
    assert str(UUID(generated)) == generated
    assert generated != request_id


def test_duplicate_request_id_headers_are_replaced(app: FastAPI) -> None:
    with TestClient(app) as client:
        response = client.get(
            "/health", headers=[("X-Request-ID", "first"), ("X-Request-ID", "second")]
        )

    assert UUID(response.headers["X-Request-ID"]).version == 4


@pytest.mark.parametrize("path", ["/missing", "/health"])
def test_error_responses_include_request_id(app: FastAPI, path: str) -> None:
    with TestClient(app) as client:
        response = client.post(path, headers={"X-Request-ID": "error-id"})

    assert response.status_code in (404, 405)
    assert response.headers["X-Request-ID"] == "error-id"


def test_unexpected_failure_is_logged_and_returns_id_without_details(
    app: FastAPI, log_output: StringIO
) -> None:
    async def fail() -> None:
        raise RuntimeError("secret exception details")

    app.add_api_route("/fail", fail)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/fail", headers={"X-Request-ID": "failure-id"})

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "failure-id"
    assert response.text == "Internal Server Error"
    output = log_output.getvalue()
    records = [json.loads(line) for line in output.splitlines()]
    assert "secret exception details" not in output
    assert [record["message"] for record in records] == [
        "request_failed",
        "request_completed",
    ]
    assert all(record["request_id"] == "failure-id" for record in records)
    assert records[0]["exception_type"] == "RuntimeError"
    assert records[1]["status_code"] == 500


def test_unexpected_failure_is_not_swallowed(app: FastAPI) -> None:
    async def fail() -> None:
        raise RuntimeError("failure")

    app.add_api_route("/fail", fail)
    with TestClient(app) as client, pytest.raises(RuntimeError, match="failure"):
        client.get("/fail")


def test_sensitive_request_data_is_not_logged(
    app: FastAPI, log_output: StringIO
) -> None:
    with TestClient(app) as client:
        client.post(
            "/private-path?token=query-secret",
            headers={"Authorization": "Bearer header-secret"},
            content="body-secret",
        )

    output = log_output.getvalue()
    assert all(
        value not in output
        for value in ("private-path", "query-secret", "header-secret", "body-secret")
    )


def test_concurrent_request_context_is_isolated_and_cleared(
    app: FastAPI, log_output: StringIO
) -> None:
    logger = cast(logging.Logger, app.state.logger)
    context = cast(ContextVar[str | None], app.state.request_id_context)

    async def exercise() -> None:
        both_arrived = asyncio.Event()
        arrived = 0

        async def inspect_context(request: Request) -> dict[str, str | None]:
            nonlocal arrived
            arrived += 1
            if arrived == 2:
                both_arrived.set()
            await both_arrived.wait()
            logger.info("inside_request")
            assert context.get() == request.state.request_id
            return {"request_id": context.get()}

        app.add_api_route("/context", inspect_context)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:

            async def send(request_id: str) -> httpx.Response:
                response = await client.get(
                    "/context", headers={"X-Request-ID": request_id}
                )
                assert context.get() is None
                return response

            first, second = await asyncio.wait_for(
                asyncio.gather(send("first"), send("second")), timeout=5
            )
            assert first.json() == {"request_id": "first"}
            assert second.json() == {"request_id": "second"}
        logger.info("outside_request")

    asyncio.run(exercise())
    records = [json.loads(line) for line in log_output.getvalue().splitlines()]
    inside_ids = [r["request_id"] for r in records if r["message"] == "inside_request"]
    assert sorted(inside_ids) == ["first", "second"]
    assert records[-1]["request_id"] is None


def test_context_is_cleared_after_failure(app: FastAPI) -> None:
    context = cast(ContextVar[str | None], app.state.request_id_context)

    async def fail() -> None:
        raise RuntimeError("failure")

    app.add_api_route("/fail", fail)

    async def exercise() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            with pytest.raises(RuntimeError, match="failure"):
                await client.get("/fail")
            assert context.get() is None

    asyncio.run(exercise())


def test_stream_failure_preserves_sent_headers_and_clears_context(
    app: FastAPI, log_output: StringIO
) -> None:
    context = cast(ContextVar[str | None], app.state.request_id_context)

    async def chunks() -> AsyncIterator[bytes]:
        yield b"partial"
        raise RuntimeError("stream failed")

    async def stream() -> StreamingResponse:
        return StreamingResponse(chunks())

    app.add_api_route("/stream", stream)

    async def exercise() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            with pytest.raises(RuntimeError, match="stream failed"):
                await client.get("/stream", headers={"X-Request-ID": "stream-id"})
            assert context.get() is None

    asyncio.run(exercise())
    records = [json.loads(line) for line in log_output.getvalue().splitlines()]
    assert records[0]["message"] == "request_failed"
    assert records[-1]["status_code"] == 200
    assert all(record["request_id"] == "stream-id" for record in records)


def test_generated_ids_are_different_for_each_request(app: FastAPI) -> None:
    with TestClient(app) as client:
        first = client.get("/health")
        second = client.get("/health")

    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]
