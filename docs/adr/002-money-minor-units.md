# ADR-002: Money as integer minor units

- **Status:** Accepted
- **Date:** 2026-10-27
- **Deciders:** Project owner

## Context

Every payment, refund and ledger entry carries an amount. Amounts must be exact: no rounding errors, and sums must match to the last unit. Currencies differ in how many decimal places they use (for example, two for USD, zero for JPY, three for KWD), so the representation must not assume two decimals.

## Options considered

| Option | Trade-offs |
|---|---|
| Integer minor units plus an ISO 4217 currency code | Exact arithmetic and simple comparisons. Needs the currency's exponent to display an amount. |
| Decimal major units (for example `NUMERIC(19,4)`) plus a currency code | Also exact in the database, but invites rounding when values pass through code or JSON, and the scale must be chosen and enforced everywhere. |
| Floating point | Cannot represent many decimal amounts exactly, so rounding errors appear. Rejected outright for money. |

## Decision

Store and calculate every amount as an **integer number of minor units** (for example cents), in a `bigint` column, together with an **ISO 4217 currency code** (three uppercase letters). Payment and ledger amounts must be positive. The database enforces this with CHECK constraints, and the API validates it before reaching the database. The column is named `amount`, and its unit is always minor units.

## Why

- Integer arithmetic is exact, so debits and credits can be compared and summed without rounding.
- It is how payment providers represent amounts, which keeps later integrations simple.
- Integers avoid the precision and formatting problems that decimals and floats cause when values pass through JSON and different languages.
- `bigint` holds far more than any realistic payment amount.

## Consequences

**Positive**

- Ledger balance checks are exact comparisons.
- No rounding rules to maintain inside the payment logic.

**Negative and follow-ups**

- Display and input conversion must use each currency's exponent, and only at the edges of the system (API input and presentation).
- JSON numbers lose precision beyond a safe integer range in some clients, so an upper limit on the amount must be decided and enforced at the API boundary.
- Currency conversion between currencies is out of scope for this project.
- The column name does not carry the unit, so this ADR and the API documentation must state it.
