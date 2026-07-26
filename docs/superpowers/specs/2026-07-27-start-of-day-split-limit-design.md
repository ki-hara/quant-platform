# Start-of-Day Split Limit Design

## Goal

Make the backtest simulate order-time buying constraints: when a trading day starts with all configured position tiers occupied, a sale later that day must not fund or authorize a same-day replacement buy.

## Decision

Use the position count captured at the start of each trading day as the buy-eligibility boundary.

- If `starting_open_position_count >= split_count`, skip the buy evaluation for that day.
- Continue evaluating and executing sells normally.
- A sell completed that day reduces the live position count, but the freed tier becomes eligible for buying only on the next trading day.
- If the day starts below the split limit, retain the existing sell-first and then buy behavior.
- Cash checks remain in force and use the post-sell balance on days that were eligible to buy at the start.

This policy models the fact that buy and sell LOC orders are prepared before either execution is known. It avoids assuming that an expected same-day sale can create a tier or buying power for another order.

## Architecture

The change stays inside the backtest engine. At the beginning of each daily iteration, the engine records the number of open positions before processing any sells. After sells are processed, the engine rebuilds the strategy context as it does today, but it calls the buy path only when the start-of-day count was below the active mode's `split_count`.

The strategy remains responsible for its normal split-limit, price-threshold, position-size, and cash rules. The engine adds only the historical timing constraint that the strategy cannot infer after the sell has mutated the position list.

No database schema, API contract, frontend, live-trading execution, or LOC-netting behavior changes are required.

## Data Flow

For each price row after the initial row:

1. Capture `starting_open_position_count = len(open_positions)`.
2. Build the pre-trade strategy context.
3. Evaluate and execute all eligible sells.
4. Update cash, realized profit and loss, fees, trades, and `open_positions`.
5. Read the active mode's configured `split_count`.
6. If the start-of-day count was at the limit, skip buy evaluation.
7. Otherwise rebuild the context and run the existing buy signal and execution path.
8. Continue capital updates and daily snapshot creation unchanged.

## Boundary Rules

- The comparison is `>=`, not `==`, so malformed or legacy states above the configured limit are also blocked.
- The active mode for the current date determines `split_count`.
- A mode change that lowers the split count blocks buying until a later day starts below the new limit.
- A day starting with six of seven tiers remains buy-eligible. If one position sells first, the existing logic may buy one position later that day because the buy order did not depend on starting from a fully occupied ladder.
- The initial price row continues to produce no trades.
- The rule affects only buys; sell evaluation is never suppressed.

## Observability

No new persisted field is required. The absence of a buy trade on a fully occupied start day is the observable outcome. Tests should use trade dates, sides, position IDs, open-position counts, and cash balances to distinguish the blocked replacement buy from normal behavior.

If a user-facing blocked-reason trace is added later, `start_of_day_split_limit_reached` is the reserved reason. Adding such a trace is outside this change because current backtest results do not persist rejected signals.

## Testing

Add focused backtest-engine regression tests covering:

1. Seven positions at the start, one profitable sell, and a valid buy threshold on the same date: the sell executes and no buy executes.
2. The following trading day starts with six positions and meets the buy threshold: one buy executes and the ladder returns to seven positions.
3. Six positions at the start with a same-day sell and valid buy threshold: existing buy behavior remains available.
4. A configured split count other than seven: the rule follows configuration rather than a hard-coded number.
5. A mode transition with a different split count: the current date's effective mode supplies the limit.

Run the complete backend test suite after the focused tests to verify that trade ordering, fees, cash, capital updates, and summary metrics remain consistent.

## Non-Goals

- Intraday OHLC path reconstruction
- Broker-specific settlement or buying-power rules
- Live broker order validation
- Changes to LOC order netting
- Preventing all same-day sell-and-buy combinations
- UI or API changes

