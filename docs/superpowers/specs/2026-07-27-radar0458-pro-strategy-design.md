# Radar0458 Pro Strategy Design

## Goal

Add `떨사오팔 Pro` as an independent SOXL strategy without changing Dynamic Wave behavior, and add a read-only `전략 통합 주문` workspace that combines selected strategies' broker orders for convenience.

## Non-goals

- Do not add automatic Pro recommendation.
- Do not reinterpret or migrate existing Dynamic Wave positions.
- Do not make integrated-order inclusion affect strategy calculation or state.
- Do not record fills or mutate positions from the integrated-order page in the first version.
- Do not generalize Radar0458 Pro to tickers other than SOXL.

## Strategy Boundary

`radar0458_pro` is a separate strategy type from Dynamic Wave.

- Display name: `떨사오팔 Pro`
- Supported ticker: SOXL
- Operating choice: the user manually selects Pro1, Pro2, or Pro3.
- It does not use QQQ weekly RSI, safe/aggressive mode, RSI recommendation, or the Dynamic Wave Capital update schedule.
- CCI and fear/greed information may remain visible as market context but does not affect Radar0458 Pro orders.
- Existing Dynamic Wave settings, snapshots, positions, calculations, APIs, and screens retain their current semantics.
- When no Radar0458 Pro configuration exists, application behavior must remain identical to the current application.

## Pro Presets

The preset values are fixed strategy rules rather than editable tier values.

| Preset | Tier allocations | Buy threshold | Sell threshold | Maximum holding |
| --- | --- | ---: | ---: | ---: |
| Pro1 | 5%, 10%, 15%, 20%, 25%, 25% | -0.01% | +0.01% | 10 trading days |
| Pro2 | 10%, 15%, 20%, 25%, 20%, 10% | -0.01% | +1.50% | 10 trading days |
| Pro3 | 1/6 for each regular tier | -0.10% | +2.00% | 12 trading days |

Pro3 uses exact sixths internally. `16.7%` is display rounding only.

## Cycle Rules

1. A new cycle snapshots the selected Pro preset and current Capital on its first buy.
2. While any position in the cycle remains open, configuration changes are pending for the next cycle.
3. Each position keeps its entry-time preset, sell threshold, and maximum holding rule.
4. The cycle ends only after all of its positions are closed.
5. Realized profit and loss is reflected at 100% in Capital.
6. The next cycle snapshots the latest Capital.

No separate cycle table is required for the first version. Open Radar0458 Pro positions carry the cycle identifier and snapshot values needed to derive the active cycle.

## Tier Planning

Order planning uses positions occupied at the start of the trading day.

1. Select the lowest-numbered empty regular tier among tiers 1 through 6.
2. A tier that sells later that day was occupied at planning time and cannot be refilled until the next trading day.
3. A regular tier that becomes empty can be purchased again within the same cycle.
4. Tier 7 is a reserve tier. It is eligible only when tiers 1 through 6 are occupied and tier 7 is empty.
5. Tier 7 has no fixed allocation. It uses residual available cash.

For regular tiers:

```text
tier allocation = cycle Capital × preset tier ratio
quantity = floor(tier allocation ÷ LOC buy limit)
```

For reserve tier 7:

```text
quantity = floor(available cash ÷ LOC buy limit)
```

The buy LOC price is rounded down to the valid USD 0.01 tick. The sell LOC price uses ordinary rounding to USD 0.01. Existing fee and LOC close-fill conventions are reused through shared interfaces, without routing Radar rules through Dynamic Wave calculations.

## Persisted Position Snapshot

Radar0458 Pro positions add nullable fields:

- tier number
- applied Pro preset
- cycle identifier
- cycle Capital
- entry-time sell threshold
- entry-time maximum holding days

The fields remain null for Dynamic Wave positions. Existing records are not backfilled or guessed.

If an open Radar0458 Pro position lacks required snapshot data, the system blocks new Radar orders with an explicit reason instead of deriving rules from the current configuration.

## User Interface

### Strategy Settings

- Strategy creation offers Dynamic Wave or Radar0458 Pro.
- Radar settings expose SOXL, Pro1/Pro2/Pro3, Capital, and Cash.
- Dynamic Wave-only RSI, safe/aggressive, and Capital-cycle controls are hidden.
- Fixed preset rules are shown read-only.

### Dashboard and Trading

- Radar dashboard information shows the current Pro, cycle Capital, occupied tiers, and next eligible buy tier.
- Radar order rows and positions show tier and applied Pro.
- Dynamic Wave screens retain their existing labels and behavior.

### Backtest

- Radar backtests select a Pro preset directly.
- Weekly RSI, fixed-safe, and fixed-aggressive policies do not apply.
- Dynamic Wave backtest behavior remains unchanged.

## Integrated Strategy Orders

Add a page named `전략 통합 주문`.

The page stores a separate `통합 주문 포함` preference for each strategy configuration. This preference is not an operating state:

- inclusion or exclusion does not change calculations, cycles, Capital, Cash, positions, or strategy-specific order tables;
- excluded strategies continue operating normally in their own screens;
- the preference only controls which source orders appear in this page.

### General Orders

- Collect the current orders from included strategies.
- Aggregate only orders with the same ticker, side, and LOC price.
- Keep different prices as separate broker orders.
- Sort final orders by USD price descending.
- An expandable source breakdown shows strategy name, tier when applicable, and source quantity.

### Netted Orders

- Apply the existing self-trade prevention rules after collecting all included source orders.
- Show both original integrated orders and transformed netted orders.
- Preserve source-order metadata for explanation.
- The integrated page is read-only in the first version. Fill confirmation remains in each strategy's existing trading/position screen.

This read-only boundary avoids introducing fill-allocation behavior that could mutate or couple otherwise independent strategies.

## Compatibility and Migration

- Database additions are nullable and additive.
- The Dynamic Wave engine is not refactored as part of this feature.
- Shared contracts may be extended only where strategy selection or generic order metadata requires it.
- Strategy-specific branching belongs at registry/service boundaries, not inside Dynamic Wave rules.
- Existing Dynamic Wave configuration snapshots remain snapshots within Dynamic Wave, not separate strategies.

## Verification

### Dynamic Wave regression

- Run the existing backend suite unchanged.
- Verify Dynamic Wave daily buy/sell plans, RSI recommendations, Capital updates, snapshots, and backtests retain existing results.
- Build the frontend and verify Dynamic Wave pages do not gain Radar-only fields.

### Radar0458 Pro

- Verify all preset constants and SOXL restriction.
- Verify tier allocation uses cycle Capital and not equal Dynamic Wave allocation.
- Verify lowest-empty-tier refill behavior.
- Verify a same-day sell does not free a tier until the next trading day.
- Verify reserve tier 7 eligibility and residual-cash sizing.
- Verify configuration changes take effect only in the next cycle.
- Verify position sell rules remain fixed after configuration changes.
- Verify 100% profit/loss reflection in the next cycle.
- Use the reconstructed official 2026-06-24 through 2026-07-24 daily tier sequence as a regression fixture.

### Integrated orders

- Verify inclusion changes no strategy state.
- Verify excluded strategies disappear only from the integrated page.
- Verify same-price aggregation, descending price ordering, source breakdown, and cross-strategy netting.
- Verify the page exposes no fill or position mutation action.

## Token-Efficient Execution

Implementation should reduce repeated context and duplicated work:

1. Treat this specification as the single source of truth; do not repeat site scraping or rule reconstruction.
2. Split work into narrow vertical tasks with explicit file ownership and acceptance checks.
3. Give any subagent only the relevant specification section and target files, not the full research history.
4. Use subagents only for genuinely independent implementation or review tasks; do not ask multiple agents to rediscover the same architecture.
5. Run focused tests after each task and run the full backend suite and frontend build once at the final integration checkpoint.
6. Commit each approved implementation unit separately so failures can be isolated without reconstructing context or reverting unrelated work.
7. Keep research artifacts outside the application branch and avoid adding generated comparison files to the repository.

Suggested implementation commits:

1. `feat: add radar0458 pro strategy domain`
2. `feat: add radar0458 pro cycle and tier planning`
3. `feat: add radar0458 pro settings and trading ui`
4. `feat: add radar0458 pro backtest support`
5. `feat: add integrated strategy orders`
6. `test: verify dynamic wave strategy isolation`
