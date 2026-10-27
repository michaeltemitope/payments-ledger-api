from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services.payments.api.dependencies import dependencies_ready


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    status: Literal["ready"]


class NotReadyResponse(BaseModel):
    status: Literal["not_ready"]


def create_health_router() -> APIRouter:
    router = APIRouter()
    router.add_api_route(
        "/health", health, methods=["GET"], response_model=HealthResponse
    )
    router.add_api_route(
        "/ready",
        ready,
        methods=["GET"],
        response_model=ReadyResponse,
        responses={503: {"model": NotReadyResponse}},
    )
    return router


async def health() -> HealthResponse:
    return HealthResponse(status="ok")


def ready(
    reachable: Annotated[bool, Depends(dependencies_ready)],
) -> ReadyResponse | JSONResponse:
    if reachable:
        return ReadyResponse(status="ready")
    return JSONResponse(status_code=503, content={"status": "not_ready"})
