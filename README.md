# Payments Ledger API

A small FastAPI backend for creating and retrieving payments stored in PostgreSQL,
with Redis and PostgreSQL readiness checks. The current API creates payments with
status `created`. Idempotency enforcement, payment transitions, ledger writes, and
event publishing are planned; they are not implemented yet.

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

Start the services with `make up`, run `make migrate`, then export
the local environment and run the integration tests:

```sh
set -a
. ./.env
set +a
make test-integration
```

The target also loads `.env`; exported variables take precedence. Integration
tests use real PostgreSQL and Redis through `PAYMENTS_TEST_DATABASE_URL` and
`PAYMENTS_TEST_REDIS_URL`. The test database name must end in `_test` and differ
from the application database name. The example selects `payments_test`,
separate from `payments`.

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
running app's `/docs` for request/response schemas. Payment creation returns 201
with a `Location` header; retrieving a missing payment returns 404, and invalid
request data returns 422.

`/health` returns 200 when the process is up. `/ready` returns 200 when PostgreSQL
and Redis are reachable, or 503 when either dependency is unavailable.

Requests accept an `X-Request-ID` containing 1 to 128 ASCII letters, digits, `.`,
`_`, or `-`; a missing or invalid value is replaced with a generated UUID.
The request ID is included in request logs and returned in the `X-Request-ID`
response header.

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

### Security scanning policy

Trivy scans OS and application-library vulnerabilities in the final runtime image.
The gate fails on HIGH and CRITICAL findings with an available fix (exit code 1,
`ignore-unfixed: true`). It deliberately ignores unfixed findings because no
package fix is available to apply. A separate report-only scan of the same image
(exit code 0, `ignore-unfixed: false`) logs all HIGH and CRITICAL findings,
including unfixed ones. Each scan has a five-minute timeout; scanner errors in
the gate also fail the job. Builder-only and development dependencies are outside
this image scan.
The workflow file is the source of truth for versions and scan settings; its
presence does not establish that a GitHub run has passed.
