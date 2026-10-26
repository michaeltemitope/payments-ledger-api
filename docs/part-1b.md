# Part 1b: local verification

The owner starts and stops services. These instructions use disposable local
credentials; replace them for your environment. URL-encode credentials in URLs.
Do not reuse production credentials or point the tests at production.

Create an untracked `.env` in the repository root (the example below is local only):

```dotenv
POSTGRES_USER=payments
POSTGRES_PASSWORD=change_me_local_only
POSTGRES_DB=payments
POSTGRES_TEST_DB=payments_test
PAYMENTS_ENVIRONMENT=development
PAYMENTS_DATABASE_URL=postgresql+psycopg://payments:change_me_local_only@postgres:5432/payments
PAYMENTS_REDIS_URL=redis://redis:6379/0
PAYMENTS_TEST_DATABASE_URL=postgresql+psycopg://payments:change_me_local_only@127.0.0.1:5432/payments_test
PAYMENTS_TEST_REDIS_URL=redis://127.0.0.1:6379/0
```

Run from the repository root:

```sh
make up
make migrate
set -a
. ./.env
set +a
make lint
make test-unit
make test-integration
```

`make up` builds the image, waits for PostgreSQL and Redis, applies migrations
through a one-shot container, and waits for the API readiness check. `make migrate`
can reapply the migration command safely. `make down` stops containers and retains
the database volume. The test database is created only on the first PostgreSQL
volume initialization; existing volumes must already have a separate test database.

Tests require an explicitly configured database name ending in `_test` and reject
an application database with the same name. They migrate, reverse migrations, and
delete payment data in that test database. Use a dedicated database with no other
clients; do not run this suite concurrently against the same database.
The Redis checks only issue `PING` and do not modify keys.

The container URLs use Compose hostnames; a host-run app instead needs PostgreSQL
and Redis URLs using `127.0.0.1`. Settings never load `.env` implicitly. The Compose
Make targets explicitly read `.env`; the shell commands above export it for tests.
The app binds to loopback by default; Compose sets `PAYMENTS_LISTEN_HOST=0.0.0.0`
inside its container and publishes ports on host loopback only. Optional host ports
are `POSTGRES_PORT`, `REDIS_PORT`, and `PAYMENTS_PORT`; update test URLs accordingly.

## API checks

```sh
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/ready
curl -i -X POST http://127.0.0.1:8000/v1/payments \
  -H 'Content-Type: application/json' -H 'X-Request-ID: local-check' \
  -d '{"amount":1234,"currency":"USD"}'
```

Follow the returned `Location` with a GET. Create returns 201, unknown IDs return
404, malformed UUIDs and invalid input return 422, and storage outages return 503.
Every response includes `X-Request-ID`. No idempotency header is required or
processed yet. No ledger entries are written yet.

Amounts are strict integer minor units, from 1 through PostgreSQL's signed bigint
maximum. Currency must be an uppercase code in the checked-in SIX ISO 4217 List One
snapshot; the source and publication date are recorded in
`services/payments/domain/currencies.py`. This includes ISO fund, metal and special
purpose codes; processor-specific support is outside this part.

## Owner completion

Write the final decisions in ADR-002 and ADR-003 in your own words. Their context
and options are drafts. After verification, update the Current status in AGENTS.md.
Part 1c (CI, security scanning, `.env.example` and minimal README) remains separate.
