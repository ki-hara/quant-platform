# Gold Toilet Order Interpreter Design

## Goal

Add a dedicated authenticated page that turns a manually entered Gold Toilet order sheet into three broker-ready values as soon as the SOXL regular-session opening price is available: breakout buy price, one shared order quantity, and LOC buy price.

## Scope

- Store one owner-specific Gold Toilet Capital and Cash balance.
- Store one manual order sheet per US market order date.
- Read the exact 09:30 America/New_York SOXL one-minute bar from Yahoo, with a separate manual override.
- Calculate both buy prices to USD cents and calculate the shared quantity from the lower LOC price.
- Present only the two prices and shared quantity as primary outputs, with copy actions.
- Warn, without changing the result, when Cash cannot reserve both orders.
- Do not monitor intraday prices, send alerts, submit broker orders, import Quanters data, or record fills.

## Calculation

```text
allocation amount = Capital * allocation percent / 100
breakout buy price = round_to_cent(open * (1 + entry percent / 100))
LOC buy price = round_to_cent(open * (1 + LOC percent / 100))
shared order quantity = floor(allocation amount / LOC buy price)
required reservation cash = quantity * (breakout buy price + LOC buy price)
```

Both Meritz orders use the same quantity. Cash shortage is advisory because the page is an interpreter, not an execution system.

## Data Flow

The user saves Capital/Cash and the next order date's percentages before the market opens. On the order date the page polls its own API every five seconds while no opening price is available. The backend asks Yahoo for the SOXL one-minute chart and accepts the open as soon as the exact 09:30 America/New_York regular-session bar appears with a positive, finite opening value. The one-minute bar does not need to close first. High and low are optional while the bar is forming; when either is present, it is validated against the open. The service never falls back to a daily candle or previous-day value. A missing or invalid bar moves from `waiting` to `failed` at 09:35, but polling continues and can recover automatically.

Automatic, manual, and effective prices are separate fields. The automatic snapshot uses source `yahoo_1m_regular_session`; an explicit manual override can be set only after the automatic price exists. Saving percentage inputs never submits a price, and clearing the override restores the preserved automatic value.

## Boundaries

- Decimal arithmetic and validation live in the backend service.
- Persistence is owner-scoped and isolated from existing strategy configurations.
- The Yahoo one-minute lookup is behind a small provider boundary so tests use a deterministic fake.
- FinanceDataReader daily candles remain valid for completed daily history, but are forbidden for same-day opening-price execution.
- The frontend renders server-calculated results and never duplicates financial arithmetic.

## Errors and Safety

- Reject non-positive Capital, negative Cash, allocation outside `(0, 100]`, or percentages at or below `-100`.
- Return `waiting`, `ready`, or `failed` without failing the whole page; keep retrying every five seconds after a validation failure.
- Show order date, price source, and observation time beside the results.
- Never reuse a sheet from a different order date implicitly.

## Verification

- Unit tests cover cent rounding, LOC-based quantity, zero quantity, and Cash warning.
- Service tests cover automatic opening-price snapshot and manual override.
- API tests cover authentication, owner isolation, persistence, validation, and waiting state.
- Migration tests cover upgrading an existing SQLite database.
- Frontend tests cover polling eligibility and copy-value formatting.
- Run the complete backend suite, frontend tests, and production frontend build.
