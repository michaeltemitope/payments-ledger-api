FROM python:3.12.15-slim-bookworm AS builder
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

FROM python:3.12.15-slim-bookworm AS runtime
RUN groupadd --gid 10001 payments && useradd --uid 10001 --gid payments --no-create-home payments
WORKDIR /app
COPY --from=builder --chown=payments:payments /app/.venv /app/.venv
COPY --chown=payments:payments services ./services
COPY --chown=payments:payments migrations ./migrations
COPY --chown=payments:payments alembic.ini ./
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "services.payments"]
