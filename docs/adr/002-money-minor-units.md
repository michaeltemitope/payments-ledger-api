# ADR-002: Money as integer minor units

- **Status:** Accepted
- **Date:** 2026-10-27
- **Decided by:** Project owner

## Context

Every payment, refund and ledger entry in this project has an amount, and money is the one thing I can't be roughly right about. Amounts have to be exact, and sums have to match to the last unit. On top of that, currencies don't all use two decimal places: the US dollar uses two, the Japanese yen uses none, and the Kuwaiti dinar uses three. Whatever I choose can't assume two decimals.

## Options I considered

**Integer minor units plus a currency code.** The amount is a whole number of the smallest unit (cents, for example) and the currency is an ISO 4217 code such as `USD`. Arithmetic is exact and comparisons are simple. The catch is that I need to know a currency's number of decimals when I show an amount to a person.

**Decimal major units plus a currency code.** Something like `NUMERIC(19,4)` in the database. It is also exact in storage, but it invites rounding as soon as the value passes through application code or JSON, and I would have to choose and enforce the scale everywhere.

**Floating point.** It can't represent many decimal amounts exactly, so rounding errors creep in. I ruled this out immediately for money.

## Decision

I store and calculate every amount as an **integer number of minor units**, in a `bigint` column, next to an **ISO 4217 currency code** (three uppercase letters). Amounts on payments and ledger entries must be positive. The database enforces that with CHECK constraints, and the API validates it before a request gets that far.

The column is simply called `amount`, and its unit is always minor units. The name doesn't say so, so this decision and the API documentation have to.

## Why

- Whole-number arithmetic is exact. When I get to the ledger, checking that debits equal credits is a plain comparison with no rounding rules to argue about.
- It matches how payment providers represent amounts, which keeps later integrations simple.
- Integers survive trips through JSON and between languages without the precision and formatting surprises that decimals and floats cause.
- A `bigint` is far larger than any real payment amount.

## Consequences

**What this gives me**

- Exact ledger checks and no rounding logic inside the payment code.

**What I have to handle**

- Converting between minor units and a displayed amount needs each currency's number of decimals, and it should only happen at the edges of the system: when input arrives and when output is shown.
- Some JSON clients lose precision on very large integers, so I need to decide on an upper limit for amounts and enforce it at the API boundary. I haven't set that limit yet.
- Converting between currencies is out of scope for this project.
