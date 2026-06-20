# Daily Trading Plan, Chart, and RSI Mode Design

## 1. Purpose

Extend the Dynamic Wave strategy platform with the three missing operational capabilities:

1. Calculate the next trading session's AOD buy limit price and quantity from the last completed session.
2. Display the selected investment symbol's price chart with volume, AOD, and trade markers.
3. Calculate an exact QQQ weekly RSI recommendation while keeping the user's confirmed live mode under manual control.

The live dashboard and backtest engine must reuse the same strategy and mode-calculation code. The frontend displays backend results and does not reproduce financial calculations.

## 2. Confirmed Product Decisions

- AOD buy limit price uses the previous completed session's close.
- AOD quantity uses Capital, not Cash, divided by the confirmed mode's split count.
- RSI recommendation is informational until the user applies it.
- A new recommendation never changes the confirmed live mode automatically.
- The existing confirmed mode remains active until the user applies the recommendation or selects Safe/Aggressive manually.
- The chart defaults to six months and supports 1 month, 3 months, 6 months, and 1 year.
- The dashboard uses one integrated layout with the live mode, recommendation, AOD plan, investment chart, and QQQ RSI panel.
- Backtests support automatic RSI mode, fixed Safe mode, and fixed Aggressive mode.

## 3. Verified RSI Formula and Rules

### 3.1 Formula

The mode indicator is calculated from QQQ unadjusted weekly closing prices:

- Resample daily QQQ prices to the last available close of each Friday-ending market week.
- Calculate RSI(14) with simple rolling averages, not Wilder/RMA smoothing.
- Compare the previous completed week's RSI with the current completed week's RSI.
- Apply the resulting recommendation to the following market week.

The formula reproduced the public report values `49.36 -> 53.60` and all 156 weekly modes in the supplied 2023-2025 backtest workbooks.

### 3.2 Safe Recommendation

- `S1`: previous RSI is at least 65 and current RSI is lower.
- `S2`: previous RSI is between 40 and 50 inclusive and current RSI is lower.
- `S3`: previous RSI is at least 50 and current RSI falls below 50.

### 3.3 Aggressive Recommendation

- `A1`: previous RSI is at most 50 and current RSI rises above 50.
- `A2`: previous RSI is between 50 and 60 inclusive and current RSI is higher.
- `A3`: previous RSI is at most 35 and current RSI is higher.

Safe rules are evaluated before aggressive rules. If no rule matches, the previous recommendation remains unchanged. Each recommendation records the matching rule code and both RSI values.

### 3.4 Evidence

- Supplied workbooks: `rsi/backtest_results*.xlsx`
- Public original analysis: `https://github.com/algori-c/DSS_public/blob/75e76192/weekly_analysis.md`
- Public original weekly report: `https://github.com/algori-c/DSS_public/blob/75e76192/weekly_report.md`

The implementation will include a regression fixture derived from the workbook dates and modes. The proprietary application code is not copied.

The public weekly report describes the `49.36 -> 53.60` transition as `A2`, while the
published rule definitions classify it as `A1` because the previous RSI is at most 50
and the current RSI crosses above 50. The implementation follows the published numeric
conditions and records `A1`. This label discrepancy does not change the resulting
Aggressive mode, and those numeric conditions reproduce all supplied weekly modes.

## 4. Architecture

### 4.1 Strategy Engine

Add a reusable `WeeklyRsiModeResolver` to the strategy engine. It accepts completed weekly closes and the prior recommendation, then returns:

- effective market week
- previous RSI
- current RSI
- recommended mode
- matched rule code, or no-change
- data-as-of date

The resolver is deterministic and independent of repositories, HTTP, and the frontend.

Refactor Dynamic Wave AOD calculation into one pure strategy operation used by live planning and backtesting. The operation accepts the previous close, confirmed/effective mode, Capital, Cash, open positions, fees, and strategy settings.

### 4.2 Application Services

`ModeRecommendationService`

- Loads the configured RSI symbol's cached prices.
- Builds completed weekly closes.
- Invokes `WeeklyRsiModeResolver`.
- Persists the recommendation snapshot for traceability.

`ModeConfirmationService`

- Loads the strategy's current mode state.
- Confirms Safe or Aggressive manually, or applies the current recommendation.
- Never changes a confirmed mode merely because a new recommendation exists.

`DailyTradingPlanService`

- Uses the last completed investment-symbol session and the confirmed mode.
- Calculates the next actual market session's AOD limit price and quantity.
- Returns explicit availability and blocking reasons.

`ChartService`

- Returns ordered investment-symbol OHLCV data for the selected range.
- Adds the current AOD line and persisted live trade markers.
- Returns QQQ weekly RSI points, threshold guides, and mode-transition markers.

### 4.3 Market Data Flow

On dashboard entry and explicit refresh:

1. Refresh the investment symbol's daily prices for at least one year.
2. Refresh the RSI symbol's daily history with enough lookback to form RSI(14), including initialization history.
3. Cache prices through the existing market-data repository.
4. Recalculate the weekly recommendation.
5. Recalculate the daily trading plan using the confirmed mode.
6. Return chart and dashboard data.

A refresh is an explicit POST operation. Read endpoints do not silently mutate cached market data.

## 5. Domain and Persistence

### 5.1 Strategy Mode State

Add a one-to-one mode state owned by a strategy configuration:

- strategy config ID
- confirmed mode
- confirmed source: `manual` or `recommendation_applied`
- confirmed timestamp
- current recommended mode
- recommendation effective week
- recommendation data-as-of date
- previous RSI
- current RSI
- recommendation rule code
- recommendation calculation timestamp

The owner relationship continues through the strategy configuration, preserving the existing future multi-user boundary.

### 5.2 Recommendation History

Persist one immutable recommendation record per strategy configuration and effective week. Recalculation for the same week is idempotent. This history supports explanation, debugging, CSV export, and regression analysis.

### 5.3 Daily Trading Plan DTO

The plan response contains:

- plan date
- market data as-of date
- investment symbol
- confirmed mode
- recommended mode and whether it differs
- recommendation rule and RSI values
- previous close
- mode buy threshold
- AOD limit price
- Capital
- split count
- per-order allocation
- calculated quantity
- estimated buy fee
- estimated required cash
- current Cash
- open-position count and limit
- buy availability
- blocking reason

Plans are calculated on demand and are not treated as executed trades.

## 6. Financial Calculations

```text
AOD limit price = previous close * (1 + mode buy threshold / 100)
Per-order allocation = Capital / mode split count
Quantity = floor(Per-order allocation / AOD limit price)
Estimated fee = AOD limit price * Quantity * fee rate / 100
Estimated required cash = AOD limit price * Quantity + Estimated fee
```

The displayed quantity follows the confirmed formula and is not reduced merely to fit Cash. Instead, the plan is marked unavailable when estimated required cash exceeds Cash. It is also unavailable when quantity is zero or the open-position count reaches the confirmed mode's split count.

The AOD plan is a limit-order instruction, so slippage is not added to its displayed
limit price or quantity. Slippage remains an execution and backtest fill assumption;
fees are included in estimated required Cash because they are charged in addition to
the order value.

The backtest calculates the same AOD price from the preceding session before evaluating the current session. It must not use the current close to create the current day's threshold.

## 7. REST API

```text
POST /api/strategy-configs/{id}/market-data/refresh
GET  /api/strategy-configs/{id}/daily-plan
GET  /api/strategy-configs/{id}/chart?range=1m|3m|6m|1y
GET  /api/strategy-configs/{id}/mode-recommendation
PUT  /api/strategy-configs/{id}/confirmed-mode
GET  /api/strategy-configs/{id}/mode-recommendations
```

`PUT confirmed-mode` accepts either a direct `safe`/`aggressive` selection or `apply_recommendation`. Applying a recommendation fails with a validation error when no current recommendation is available.

Chart responses use typed DTOs for candlesticks, volume, RSI points, horizontal guides, AOD, and trade/mode markers. The API returns numeric values as decimal strings where precision matters.

## 8. Dashboard UX

The approved integrated dashboard is ordered as follows:

1. Confirmed live mode with Safe/Aggressive segmented controls.
2. RSI recommendation, previous/current values, rule code, and `Apply recommendation` action.
3. A mismatch warning when confirmed and recommended modes differ.
4. Today's AOD limit price, quantity, formula inputs, availability, and reason.
5. Investment-symbol daily candlestick chart with volume, AOD line, and buy/sell markers.
6. QQQ weekly RSI(14) panel with guides at 35, 40, 50, 60, and 65 plus mode-transition markers.

The chart defaults to six months. Range controls are 1 month, 3 months, 6 months, and 1 year. The chart is an operational tool, not a decorative card, and keeps stable responsive dimensions.

## 9. Error and Staleness Handling

- Fewer than 15 completed weekly closes: recommendation unavailable; confirmed mode remains unchanged.
- Missing previous investment close: AOD plan unavailable.
- Market refresh failure: show the last data-as-of date and the refresh error; never label stale data as current.
- Holiday: retain the last completed close and label the plan for the next actual session without creating duplicate plans.
- Unknown mode state: initialize the confirmed mode to Safe and require a visible user confirmation before changing it.
- Missing recommendation: disable `Apply recommendation` while manual Safe/Aggressive selection remains available.

## 10. Backtest Integration

Backtest mode policy is part of the run snapshot:

- `weekly_rsi`: exact automatic S1-S3/A1-A3 resolver, default
- `fixed_safe`
- `fixed_aggressive`

Weekly RSI decisions use only data completed before the effective week. The backtest result stores the effective mode and rule code for each daily snapshot so mode transitions can be charted and exported.

## 11. Testing and Acceptance

### 11.1 Strategy Tests

- Weekly simple RSI(14) calculation.
- Boundary behavior for 35, 40, 50, 60, and 65.
- S1-S3 and A1-A3 independently.
- Safe-rule precedence and no-change behavior.
- Holiday-shortened weeks use the last available weekly close.
- Effective mode begins in the following market week.

### 11.2 Regression Tests

- Reproduce `49.36 -> 53.60`, rule A1, Aggressive recommendation.
- Reproduce all 156 supplied 2023-2025 weekly modes with zero mismatches.
- Verify no future data is used.

### 11.3 AOD and Service Tests

- Exact AOD price and quantity formula.
- Capital rather than Cash controls allocation.
- Fee, insufficient Cash, zero quantity, and split-limit behavior.
- Existing confirmed mode survives a new recommendation.
- Applying a recommendation and direct manual confirmation.
- Range-filtered, sorted chart DTOs and marker placement.

### 11.4 Frontend and Browser Tests

- Confirmed/recommended mismatch state.
- Manual mode controls and Apply action.
- AOD inputs and blocking reasons are visible in Korean.
- Candlestick, volume, AOD, trade markers, and RSI panel render nonblank.
- Desktop and mobile layouts do not overlap.
- Browser console has no errors.

## 12. Out of Scope

- Brokerage order submission or automatic trading.
- Background scheduling that changes the confirmed live mode.
- Intraday RSI or intraday candlesticks.
- Reverse engineering or copying non-public proprietary backend code.
