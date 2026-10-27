# ADR-003: Database transactions and locking

- **Status:** Accepted
- **Date:** 2026-10-27
- **Decided by:** Project owner

## Context

Several things I'm about to build only work if they behave correctly when requests arrive at the same time:

- Two requests might try to create the same payment (idempotency, part 2b).
- Two requests might try to change the same payment at once, such as a capture and a refund (part 2a).
- A payment, its ledger entries and its outbox event must all succeed or all fail together (parts 3a and 3b).

The database is the only place where these guarantees can be enforced reliably, so I want to settle the transaction and locking approach before writing the code that depends on it.

## Options I considered

**`READ COMMITTED` with constraints and row locks where needed.** This is PostgreSQL's default isolation level. It is simple and predictable, and I deal with each contention point on purpose. The risk is that I have to find those points myself.

**`SERIALIZABLE` everywhere.** The strongest guarantee without thinking about each case. But transactions can fail with serialization errors, so every transaction would need retry handling, and throughput drops when requests compete.

**Advisory locks.** Flexible, but the lock isn't tied to a row, so it is easier to forget or to scope wrongly, and harder to reason about when I read the code later.

## Decision

I'm using PostgreSQL's default **`READ COMMITTED`** isolation level, and I handle each known contention point explicitly:

1. **Constraints come first.** Unique, CHECK and foreign key constraints are my first line of defense. The unique idempotency key in part 2b is the main example.
2. **State changes lock the payment row.** Before changing a payment's state, I lock that row with `SELECT ... FOR UPDATE`, so two concurrent changes to the same payment run one after the other (part 2a).
3. **One short transaction per request,** owned by the service layer. A payment, its ledger entries and its outbox event are written in the same transaction.
4. **Locks are taken in a consistent order.** When a transaction locks more than one row, it always does so in the same order (the payment first, then its ledger entries), so two transactions can't wait on each other forever.
5. **No remote calls while holding row locks.** Network calls to the ledger service or Kafka must not happen inside a transaction that holds locks. How the ledger call fits this rule is something I'll decide in part 3a.

## Why

Concurrency in this system happens at a few clear points: one payment row and one idempotency key. I can handle each one explicitly and prove it with a concurrency test. `SERIALIZABLE` would add retry logic to every transaction for very little gain when I already know where the contention is. Constraints and row locks are also visible in the schema and in the code, so a reader can see which guarantee protects which rule.

## Consequences

**What this gives me**

- Predictable behavior and simple transaction code.
- Every guarantee backed by a concurrency test.

**What I have to watch**

- Nothing catches a contention point I forgot, so the tests have to cover each one.
- Waiting for a row lock needs a limit. I'll set lock and statement timeouts when I add the first row lock in part 2a, so contention fails quickly instead of hanging.
- The isolation level is currently the database default. I'll set it explicitly in the engine configuration the next time I touch that code, so the choice is visible in the code and not just in this document.

**When I would revisit this**

- If concurrency tests or load tests (part 6a) show problems that row locks and constraints can't prevent.
