# ADR-003: Database transactions and locking

- **Status:** Accepted
- **Date:** 2026-10-27
- **Deciders:** Project owner

## Context

Several parts of this project depend on correct behavior under concurrent requests:

- Two requests may try to create the same payment (idempotency, part 2b).
- Two requests may try to change the same payment at once, for example capture and refund (part 2a).
- A payment, its ledger entries and its outbox event must all succeed or fail together (parts 3a and 3b).

The database is the only place where these guarantees can be enforced reliably, so the transaction and locking approach must be decided before the code that depends on it.

## Options considered

| Option | Trade-offs |
|---|---|
| `READ COMMITTED` (PostgreSQL default), with constraints and explicit row locks where needed | Simple and predictable. Each contention point is handled deliberately. Requires care to find those points. |
| `SERIALIZABLE` everywhere | Strongest guarantee without thinking about each case, but concurrent transactions can fail with serialization errors, so every transaction needs retry handling and throughput drops under contention. |
| Advisory locks | Flexible, but the lock is not tied to a row, so it is easier to forget or mis-scope, and harder to reason about. |

## Decision

Use PostgreSQL's default **`READ COMMITTED`** isolation level, and handle each known contention point explicitly:

1. **Database constraints first.** Unique, CHECK and foreign key constraints are the first line of defense (for example, the unique idempotency key in part 2b).
2. **Row locks for state changes.** Any change to a payment's state first locks that payment row with `SELECT ... FOR UPDATE`, so two concurrent changes to the same payment run one after the other (part 2a).
3. **One short transaction per request,** owned by the service layer. A payment and its ledger entries and outbox event are written in the same transaction.
4. **Consistent lock order.** If a transaction locks more than one row, it always locks them in the same order (the payment before its ledger entries) to avoid deadlocks.
5. **No remote calls while holding row locks.** Network calls (the ledger service, Kafka) must not run inside a transaction that holds locks. How the ledger call fits this rule is decided in part 3a.

## Why

- Concurrency in this system happens at a few clear points (one payment row, one idempotency key), and each can be handled explicitly and tested with concurrency tests.
- `SERIALIZABLE` would add retry logic everywhere and reduce throughput, for little benefit when the contention points are known.
- Row locks and constraints are visible in the code and in the schema, so a reader can see which guarantee protects which rule.

## Consequences

**Positive**

- Predictable behavior and simple transaction code.
- Each guarantee is backed by a concurrency test.

**Negative and follow-ups**

- A missed contention point is not caught automatically, so tests must cover each one.
- Waiting on a row lock needs a limit. Set lock and statement timeouts when the first row lock is introduced (part 2a), so contention fails fast instead of hanging.
- The isolation level is currently the database default. Set it explicitly in the engine configuration the next time that code is touched, so the choice is visible in code.

**Revisit when**

- Concurrency tests or load tests (part 6a) show anomalies that row locks and constraints cannot prevent.
