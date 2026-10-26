# ADR-002: Money representation

- **Status:** Draft — owner decision pending

## Context

Payment amounts must preserve exact values through JSON, Python and PostgreSQL.
Binary floating point cannot represent every decimal amount exactly. Currencies
have different minor-unit conventions; this API receives already-denominated
minor units and does not perform major-unit conversions.

## Options

- Integer minor units plus ISO 4217 code: exact arithmetic and straightforward
  database constraints; clients must know the currency's minor-unit convention.
- Decimal major units plus ISO 4217 code: familiar human representation; requires
  explicit precision, scale, rounding and serialization rules.
- Floating point: familiar JSON representation, but unsuitable for exact money.

## Decision

To be written by the owner in their own words.

## Consequences to consider

The implementation follows the Phase 1 requirement: positive integer minor units
stored in PostgreSQL bigint, validated before database access, paired with an
uppercase ISO 4217 code. Values exceeding bigint are rejected, as are booleans,
strings and floats. Currency reference data needs deliberate updates. Clients
using JavaScript must preserve integer precision for values above its safe integer
range; this part has no conversion or exchange-rate behavior.
