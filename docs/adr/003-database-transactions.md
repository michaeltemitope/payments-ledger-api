# ADR-003: Initial database transactions

- **Status:** Draft — owner decision pending

## Context

Part 1b creates one payment or retrieves one payment per request. It does not yet
implement idempotency, state transitions, ledger writes or an outbox.

## Options

- PostgreSQL default READ COMMITTED: simple single-request transactions; future
  multi-step concurrent operations need constraints or deliberate locking.
- SERIALIZABLE: broader isolation, but requires serialization-failure handling
  and retry policy even for otherwise simple operations.
- Explicit row or advisory locks: useful for selected concurrent operations;
  no existing payment row needs mutation or coordination in this part.

## Decision

To be written by the owner in their own words.

## Consequences to consider

The implementation uses READ COMMITTED without explicit locks. Each service call
owns a transaction and commits before returning a successful response; failures
roll back. Sessions are request-scoped. The reserved idempotency key has a unique
constraint, but is unused in this part. Revisit isolation and locking explicitly
when Phase 2 introduces concurrent idempotent requests and payment transitions.
Database connections, pool acquisition and SQL statements have configured timeouts.
