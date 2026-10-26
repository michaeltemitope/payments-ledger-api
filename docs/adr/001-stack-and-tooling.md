# ADR-001: Stack and tooling

- **Status:** Accepted
- **Date:** 2026-10-26
- **Deciders:** Project owner

## Context

This project is a small payments and ledger API. Phase 1 has to give the rest of the project (idempotency, ledger, outbox, observability, API versioning) a base that does not need to be reworked later.

What matters most, in order:

1. **Correctness.** The code handles money and payment state, so wrong types and silent errors are expensive.
2. **Reproducibility.** The same install must work on my machine, for the coding agent, and in CI.
3. **Fast feedback.** Lint, type checks and unit tests must run in seconds.
4. **Clarity.** Transactions and failure handling must be easy to read and reason about.
5. **Small toolset.** Every tool must be one I can explain and maintain.

Fixed by the project: Python 3.12, FastAPI, PostgreSQL, Redis, Docker and GitHub Actions. Development happens in WSL, with a coding agent (Codex) working in small, reviewed steps.

## Decisions

### 1. Dependency manager: uv

| Option | Trade-offs |
|---|---|
| uv | One tool for the Python version, the virtual environment and the lockfile. Fast. Newer than the alternatives. |
| Poetry | Mature and integrated, but brings its own workflow and conventions. |
| pip + pip-tools | Familiar, but the environment and lock generation are managed by hand. |

**Decision:** uv, with exact version pins for direct dependencies and a committed `uv.lock`. Every command runs with `uv run --locked`, so it fails if the lockfile is out of date, locally and in CI.

**Why:** one tool gives everyone the same environment, and a stale lockfile cannot slip through unnoticed.

### 2. Linting and formatting: Ruff

| Option | Trade-offs |
|---|---|
| Ruff (lint, import sorting, format) | One tool and one config. Very fast. Rule selection needs care. |
| Ruff lint + Black | Separate responsibilities, but an extra tool. |
| Flake8 + Black + isort | Specialized tools, but more dependencies and more config to maintain. |

**Decision:** Ruff for linting, import sorting and formatting. The rule set is selected explicitly in `pyproject.toml` (not just the defaults) and covers common bug patterns, import order, outdated syntax and security checks. Any ignored rule needs a written reason next to it.

**Why:** the smallest toolset that covers all three jobs, and explicit rules mean lint failures mean something.

### 3. Type checking: mypy in strict mode

| Option | Trade-offs |
|---|---|
| mypy (strict) | Python-native workflow, configurable. Framework typing sometimes needs configuration. |
| Pyright | Strong inference and editor support, but its command line adds a Node-based toolchain or wrapper. |

**Decision:** mypy in strict mode, covering application code and tests.

**Why:** money amounts, payment states and idempotency records are where a wrong type causes real bugs, and I want the checker to catch them before runtime.

### 4. Database access: synchronous SQLAlchemy (from part 1b)

| Option | Trade-offs |
|---|---|
| Sync SQLAlchemy 2.x | Straightforward transactions and debugging. Blocking calls run in FastAPI's worker threadpool. |
| Async SQLAlchemy 2.x | Fits asynchronous I/O, but needs explicit awaits, careful session lifetimes and avoiding implicit lazy loading. |

**Decision:** synchronous SQLAlchemy. No database code is written in part 1a. The PostgreSQL driver is chosen in part 1b.

**Why:**
- The API is database-bound: each request is a short transaction. The real concurrency ceiling is the connection pool and PostgreSQL's connection limit, and async code does not raise that ceiling.
- Idempotency, ledger writes and the outbox depend on explicit transactions, unique constraints and row locks. Synchronous code keeps the transaction boundaries and failure paths easy to read, test and debug.
- The outbox relay and the consumer are separate processes, so they do not depend on the web framework's concurrency model.

**Risk and revisit trigger:** synchronous endpoints run on a bounded worker threadpool (40 threads by default), so the pool size and the thread limit must be set together. Reconsider async only if load testing (part 6a) shows requests queueing on threads while the database pool still has headroom.

### 5. Supporting libraries

- `pydantic-settings` for typed configuration that fails fast when required settings are missing.
- `uvicorn` to serve the app.
- `httpx` for in-process endpoint tests.
- Standard-library JSON logging instead of a logging dependency, with application-owned configuration and no global side effects. A library such as structlog was considered, and can be adopted later if richer log processing is needed.

### 6. Test and quality gates

**Decision:** pytest for all tests, split into unit tests (no services needed) and integration tests (real PostgreSQL and Redis, no mocks for the database). `make lint` and `make test-unit` run the same checks locally and in CI. A coverage gate is added in part 2c.

**Why:** unit tests stay fast enough to run constantly, integration tests stay honest about database behavior, and the same gates run everywhere so a green local run means a green CI run.

## Consequences

**Positive**

- Reproducible installs and a small, understandable toolset.
- Strict typing and fast linting from the first commit.
- Simple, readable transaction handling.

**Negative and risks**

- uv is newer than Poetry or pip-tools, so its commands must be learned.
- Synchronous endpoints have a bounded threadpool, as described above.
- A deprecation warning from `httpx` appeared in part 1a and must be resolved when dependencies are upgraded.

**Revisit when**

- Load testing (part 6a) shows threadpool saturation, as described in decision 4.
- A tool in this list becomes a maintenance burden or blocks a later phase.
