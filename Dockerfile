FROM python:3.12.15-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70 AS builder
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

FROM python:3.12.15-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70 AS runtime
# Apply the OpenSSL fix for CVE-2026-84782 missing from the pinned base.
# Remove this step once the base includes libssl3 and openssl 3.0.22-1~deb12u2 or newer.
RUN apt-get update \
    && apt-get install -y --no-install-recommends --only-upgrade libssl3 openssl \
    && rm -rf /var/lib/apt/lists/*
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
