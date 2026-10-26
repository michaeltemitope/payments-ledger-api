from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    status: Literal["ready"]


def create_health_router() -> APIRouter:
    router = APIRouter()
    router.add_api_route(
        "/health", health, methods=["GET"], response_model=HealthResponse
    )
    router.add_api_route("/ready", ready, methods=["GET"], response_model=ReadyResponse)
    return router


async def health() -> HealthResponse:
    return HealthResponse(status="ok")


async def ready() -> ReadyResponse:
    return ReadyResponse(status="ready")
