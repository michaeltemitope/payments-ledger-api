# Payments Ledger API

A small FastAPI backend for creating and retrieving payments stored in PostgreSQL,
with Redis and PostgreSQL readiness checks. The current API creates payments with
status `created`. Idempotency enforcement, payment transitions, ledger writes, and
event publishing are planned; they are not implemented yet.

See [AGENTS.md](AGENTS.md) for the current phase, scope, and contributor rules.
Design decisions live in [ADR-001: stack and tooling](docs/adr/001-stack-and-tooling.md),
[ADR-002: money](docs/adr/002-money-minor-units.md), and
[ADR-003: database transactions](docs/adr/003-database-transactions.md).

## Run locally

Prerequisites: Python 3.12, uv (CI uses 0.13.5), Make, Docker with the Compose
plugin, and curl for the API examples. Run commands from the repository root.
The Make targets resolve Python dependencies from the committed `uv.lock`.

Create local configuration once, then review the fake values and URL comments:

```sh
cp .env.example .env
```

The owner starts the services and runs migrations:

```sh
make up
make migrate
```

`make up` builds the application image, starts PostgreSQL and Redis, applies
migrations through a one-shot container, and waits for API readiness.
`make migrate` safely reapplies the migration command. The default API address is
`http://127.0.0.1:8000`; interactive API documentation is available at `/docs`.

The [.env.example](.env.example) distinguishes Compose service URLs from host-run
test URLs. If you change published PostgreSQL or Redis ports, update the test URLs
too; changing `PAYMENTS_PORT` changes the port used in the API examples below.
For a host-run app, replace Compose hostnames with `127.0.0.1` and the published
ports. Application settings do not load `.env` implicitly. Compose's Make targets
and the integration-test target explicitly load it; exported variables take
precedence. Compose publishes services on host loopback and sets the app's listen
address to `0.0.0.0` inside the container.

To stop the local stack, the owner runs:

```sh
make down
```

This retains the PostgreSQL volume. The separate test database is created only
during the volume's first initialization. An existing volume must already contain
the configured test database; changing `.env` does not recreate it.

## Run checks and tests

Formatting, lint, type checks, and unit tests need no running services:

```sh
make lint
make test-unit
```

After the owner has run `make up` and `make migrate`:

```sh
make test-integration
```

This target loads `.env` itself, so no shell export is needed. It uses
`PAYMENTS_TEST_DATABASE_URL` and `PAYMENTS_TEST_REDIS_URL`. The example selects
`payments_test`, separate from `payments`; the existing safety guard still applies.
See [environment and verification rules](AGENTS.md#environment-and-verification).

The integration suite applies migrations, reverses and reapplies them, and deletes
payment data in its test database. Use a disposable database with no other clients
and run only one suite against it at a time. Redis checks issue `PING` without
modifying keys. To run both suites with services available:

```sh
make test
```

All Python check and test targets use `uv run --locked`.

## Try the API

With the default local ports:

```sh
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/ready
curl -i -X POST http://127.0.0.1:8000/v1/payments \
  -H 'Content-Type: application/json' -H 'X-Request-ID: local-check' \
  -d '{"amount":1234,"currency":"USD"}'
```

Follow the returned `Location` path with a GET at the same base address. See the
running app's `/docs` for request/response schemas and
[API standards](AGENTS.md#api-standards) for status and request-ID conventions.
No idempotency header is processed yet, and creation writes no ledger entries.

For amount units, see [ADR-002](docs/adr/002-money-minor-units.md). Accepted amounts
range from 1 through PostgreSQL's signed bigint maximum. Supported currency codes
come from the checked-in [SIX ISO 4217 snapshot](services/payments/domain/currencies.py),
including fund, metal, and special-purpose codes; processor-specific support is
not implemented.

## CI

The [GitHub Actions workflow](.github/workflows/ci.yml) runs on pull requests with
three independent jobs:

| Job | Checks | Timeout |
| --- | --- | --- |
| Quality | `make lint` (formatting, Ruff, strict mypy), then `make test-unit` | 10 minutes |
| Integration | PostgreSQL and Redis service containers, then `make test-integration`; fixtures apply migrations | 15 minutes |
| Image security | Build the runtime Docker image, save it, then scan the archive with Trivy | 20 minutes |

CI uses the same PostgreSQL and Redis image versions as Compose. PostgreSQL
initializes `payments_test`; the configured application database name is
`payments`. Integration configuration comes from job environment variables, with
dotenv loading disabled; CI needs no local `.env` or repository secrets.

Actions use full commit SHA pins. Python and uv versions are explicit, permissions
are limited to `contents: read`, and superseded runs for the same PR are cancelled.
Persistent action caches are disabled. The workflow builds locally without
publishing an image or deploying anything.

Trivy scans OS and application-library vulnerabilities in the final runtime image.
HIGH and CRITICAL findings fail the job, including findings without fixes. The
scan has a five-minute timeout; scanner errors also fail the job. Results appear
in job logs. Builder-only and development dependencies are outside this image scan.
The workflow file is the source of truth for versions and scan settings; its
presence does not establish that a GitHub run has passed.
