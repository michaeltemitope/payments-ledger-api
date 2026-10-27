# ADR-001: Stack and tooling

- **Status:** Accepted (amended after part 1b)
- **Date:** 2026-10-26, amended 2026-10-27
- **Decided by:** Project owner

## Context

This project is a small payments and ledger API. Before I write any real features, I want a base I won't regret later, because idempotency, the ledger, the outbox, monitoring and API versioning will all sit on top of it.

What I care about, roughly in this order:

1. **Correctness.** The code handles money and payment state, so a wrong type or a silent error costs more than usual.
2. **Reproducibility.** The same install has to work on my machine, for Codex, and in CI.
3. **Fast feedback.** Lint, type checks and unit tests should finish in seconds, or I'll stop running them.
4. **Clarity.** I want transactions and failure handling to be easy to read.
5. **A small toolset.** Every tool should be one I can explain and maintain.

The project already fixes Python 3.12, FastAPI, PostgreSQL, Redis, Docker and GitHub Actions. I work in WSL, and Codex does the typing in small steps that I review.

## Decisions

### Dependency manager: uv

I looked at uv, Poetry, and pip with pip-tools. Poetry is mature, but it brings its own workflow and conventions. pip-tools is familiar, but I would be managing the environment and the lock generation by hand.

I chose **uv**, with exact version pins for direct dependencies and a committed `uv.lock`. Every command runs with `uv run --locked`, so a stale lockfile makes things fail loudly instead of quietly drifting. One tool gives me, Codex and CI the same environment. The price is that uv is newer than the alternatives, so I had to learn it.

### Linting and formatting: Ruff

The alternatives were Ruff for linting plus Black for formatting, or the older Flake8, Black and isort combination. Both mean more tools and more configuration for the same result.

I chose **Ruff** for linting, import sorting and formatting. I picked the rules on purpose instead of accepting the defaults: `E`, `F`, `I`, `UP`, `B`, `S`, `C4`, `SIM` and `PT`. I added the security rules (`S`) after part 1a, because a payments service should catch things like weak randomness or unsafe SQL building early. Asserts and fake passwords are normal in tests, so `S101`, `S105` and `S106` are ignored in tests only. Any other ignored rule needs a written reason next to it.

### Type checking: mypy in strict mode

Pyright is a good checker with excellent editor support, but its command line needs a Node-based toolchain or a wrapper. I would rather keep the whole workflow in Python.

I chose **mypy in strict mode**, with the Pydantic plugin, covering both the application and the tests. Money amounts, payment states and idempotency records are exactly where a wrong type turns into a real bug, and I want the checker to catch it before the code runs.

### Database access: synchronous SQLAlchemy with psycopg 3

I considered synchronous and asynchronous SQLAlchemy. Async fits asynchronous I/O, but it needs explicit awaits, careful session lifetimes, and care to avoid implicit lazy loading.

I chose **synchronous SQLAlchemy 2.x**, and in part 1b I picked **psycopg 3** as the driver. My reasoning:

- This API is database-bound. Each request is a short transaction, so the real ceiling on concurrency is the connection pool and PostgreSQL's connection limit. Async code does not raise that ceiling.
- Idempotency, ledger writes and the outbox depend on explicit transactions, unique constraints and row locks. Synchronous code keeps those boundaries easy to read, test and debug.
- The outbox relay and the consumer will be separate processes, so they don't depend on how the web framework handles concurrency.

The risk is that synchronous endpoints run on a bounded worker threadpool (40 threads by default), so the pool size and the thread limit have to be set together. I would only reconsider async if load testing in part 6a shows requests waiting for threads while the database pool still has room.

### Supporting libraries

- **pydantic-settings** for typed configuration that fails fast when a required setting is missing.
- **uvicorn** to serve the app.
- **httpx and httpx2** for endpoint tests. Newer versions of Starlette prefer `httpx2` for their test client and warn when they fall back to `httpx`. I added `httpx2` to the dev dependencies to remove the warning, and kept `httpx` because my tests import it directly.
- **Standard-library JSON logging** instead of a logging dependency, configured by the application with no global side effects. I considered structlog and might adopt it later if I need richer log processing.

### Tests and quality gates

I use **pytest** for everything, split into unit tests that need no services and integration tests that run against real PostgreSQL and Redis, with no mocks for the database. `make lint` and `make test-unit` run the same checks locally and in CI. A coverage gate comes in part 2c.

Unit tests stay fast enough to run constantly, integration tests stay honest about how the database really behaves, and the same checks run everywhere, so a green local run should mean a green CI run.

## Consequences

**What this gives me**

- Reproducible installs and a toolset small enough to understand fully.
- Strict typing and security-aware linting from the first commit.
- Transaction code that is simple to read.

**What it costs me**

- uv is newer than Poetry or pip-tools, so I have to learn its commands.
- Synchronous endpoints share a bounded threadpool, as described above.
- Two HTTP client packages sit in the dev dependencies until my tests move fully to `httpx2`.

**When I would revisit this**

- If load testing (part 6a) shows threadpool saturation.
- If any tool becomes a maintenance burden or gets in the way of a later phase.
