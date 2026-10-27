from collections.abc import Iterator
from typing import Annotated, cast

from fastapi import Depends, Request
from redis import Redis
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from services.payments.infra.readiness import dependencies_reachable
from services.payments.service.payments import PaymentService


def get_session(request: Request) -> Iterator[Session]:
    with Session(
        cast(Engine, request.app.state.engine), expire_on_commit=False
    ) as session:
        yield session


def get_payment_service(
    session: Annotated[Session, Depends(get_session)],
) -> PaymentService:
    return PaymentService(session)


def dependencies_ready(request: Request) -> bool:
    return dependencies_reachable(
        cast(Engine, request.app.state.engine),
        cast(Redis, request.app.state.redis_client),
    )
