# Quant Strategy Research and Backtest Platform Design

## Summary

Build a personal quant strategy research and trading-support web platform. The first implemented strategy is Dynamic Wave Strategy, but the architecture must support adding future strategies with minimal changes.

The first delivery is the full platform skeleton plus the Dynamic Wave core flow:

- Separate FastAPI backend and React TypeScript frontend.
- SQLite persistence through repository interfaces, with a path to PostgreSQL later.
- Domain, DTO, service, repository, strategy engine, and backtest engine boundaries.
- FinanceDataReader as the default market data provider with SQLite caching.
- Manual-friendly live trading support: users can execute generated signals as virtual fills, then edit or correct fills when real execution differs.
- Backtest execution using the same strategy logic as live signal calculation.
- Docker and README support.

Automatic brokerage trading is out of scope.

## Scope

### In Scope

- Personal single-user operation with a default owner.
- Thin owner model in the database so future multi-user support can be added without restructuring user-owned data.
- Dynamic Wave Strategy implementation.
- Strategy settings schema returned from the backend and rendered as an auto-generated frontend form.
- Live dashboard with today buy/sell signals, portfolio metrics, open positions, and recent trades.
- Signal execution flow with editable fills.
- Manual trade correction flow.
- Backtest over a selected date range.
- Backtest metrics: CAGR, MDD, final asset value, total return, win rate, total trades, average holding period, cumulative fees.
- Lightweight Charts for asset curve, drawdown, and trade markers.
- CSV downloads for daily asset snapshots, trades, and backtest summary.
- Unit/integration test structure.

### Out of Scope

- Brokerage API integration.
- Automatic order placement.
- Full authentication, signup, password management, or authorization UI.
- Background worker infrastructure or service splitting.
- Production SaaS deployment hardening.

## Chosen Approach

Use a modular monolith backend with a separated frontend.

The backend is deployed as one FastAPI application, but internal modules are split by responsibility:

- API layer
- DTO layer
- Application service layer
- Domain layer
- Repository layer
- Strategy engine
- Backtest engine
- Market data providers
- Infrastructure and database session management

This gives the first version a manageable deployment model while preserving clear boundaries for future extraction or replacement.

## Architecture

### Backend

The backend uses FastAPI and Python 3.12+.

Responsibilities:

- Expose REST APIs.
- Validate request and response DTOs.
- Coordinate use cases in services.
- Persist data through repositories.
- Call market data providers through a provider interface.
- Run live signal calculation and backtests through the shared strategy engine.

Strategy logic is implemented once. Live trading support and backtesting both call the same strategy interface.

### Frontend

The frontend uses React, TypeScript, and Vite.

Responsibilities:

- Render dashboard, backtest, strategy settings, positions, and trades.
- Use generated strategy settings schemas to render forms.
- Display charts with Lightweight Charts.
- Type API responses explicitly in TypeScript.
- Provide CSV download actions.

The first screen is the working dashboard, not a marketing page.

### Database

SQLite is used for the first version. Database access is isolated behind repositories so PostgreSQL can be introduced later.

## Domain Model

### Owner

Represents the data owner. The first version seeds and uses one default owner.

Fields:

- `id`
- `name`

### Strategy Config

Stores a configured strategy instance.

Fields:

- `id`
- `owner_id`
- `name`
- `strategy_type`
- `symbol`
- `initial_capital`
- `fee_rate`
- `slippage_rate`
- `settings_json`
- timestamps

`settings_json` stores strategy-specific settings such as Dynamic Wave Safe/Aggressive parameters, PCR/LCR, and capital update schedule.

### Market Price

Stores normalized OHLCV cache rows.

Fields:

- `provider`
- `symbol`
- `date`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `adjusted`

The uniqueness key is provider, symbol, date, and adjusted flag.

### Live Portfolio

Stores current live portfolio state for a strategy config.

Fields:

- `strategy_config_id`
- `capital`
- `cash`
- `realized_pnl`
- `cumulative_fees`
- timestamps

Capital is strategy reference capital and is managed separately from cash.

### Position

Represents an independent buy lot. Average cost is not used.

Fields:

- `id`
- `strategy_config_id`
- `buy_date`
- `buy_price`
- `quantity`
- `mode`
- `status`
- `closed_at`
- timestamps

Holding days and current return are calculated from market data and current date.

### Trade

Stores live trades.

Fields:

- `id`
- `strategy_config_id`
- `date`
- `side`
- `quantity`
- `price`
- `fee`
- `realized_pnl`
- `sell_reason`
- `source`
- timestamps

Allowed sources include:

- `signal_execution`
- `manual`
- `correction`

### Backtest Run

Stores a backtest execution and summary.

Fields:

- `id`
- `owner_id`
- `strategy_config_snapshot_json`
- `start_date`
- `end_date`
- `status`
- `error_message`
- summary metrics
- timestamps

### Backtest Daily Snapshot

Stores daily backtest state.

Fields:

- `backtest_run_id`
- `date`
- `capital`
- `cash`
- `position_value`
- `total_asset`
- `drawdown`
- `cumulative_fees`

### Backtest Trade

Stores backtest-only trades separately from live trades.

Fields mirror live trade fields and include `backtest_run_id`.

## Market Data

The default market data provider is FinanceDataReader with SQLite caching.

Provider design:

- `MarketDataProvider` interface returns normalized OHLCV DTOs.
- `FinanceDataReaderProvider` is the default implementation.
- Future providers can include yfinance, pykrx, or CSV import.
- Backtest and strategy engines consume normalized OHLCV data and do not know the provider source.

Yahoo Finance/yfinance is not the default because it is better treated as a personal/research convenience provider and is not ideal as the primary Korean-market data source.

## Strategy Engine

All strategies implement a common interface:

```python
get_mode(context) -> StrategyMode
should_buy(context) -> BuySignal
should_sell(context, position) -> SellSignal
calculate_position_size(context) -> PositionSize
update_capital(context, realized_pnl) -> CapitalUpdate
get_settings_schema() -> SettingsSchema
```

Each method receives a context rather than reading global state. The context includes:

- current date
- current and previous prices
- strategy settings
- capital
- cash
- open positions
- relevant indicators

Strategies are registered through a strategy registry. Adding a new strategy should require adding a new strategy class and registration metadata, without modifying backtest or live dashboard logic.

## Dynamic Wave Strategy

### Mode

Modes:

- `safe`
- `aggressive`

The first version uses a placeholder mode resolver:

```python
def get_mode(context):
    return "safe"
```

The resolver is isolated so a future QQQ RSI-based implementation can replace it.

### Settings

Common settings:

- strategy name
- target symbol
- initial capital
- fee rate
- slippage rate

Dynamic Wave settings:

- target symbol
- mode RSI symbol
- base index
- profit compounding rate, PCR
- loss compounding rate, LCR
- capital update schedule
- safe split count
- safe max holding period
- safe buy threshold percent
- safe sell threshold percent
- aggressive split count
- aggressive max holding period
- aggressive buy threshold percent
- aggressive sell threshold percent

Capital update schedule supports both:

- N trading days
- calendar period such as monthly, quarterly, or yearly

The default is N trading days.

### Buy Rule

The strategy uses AOD logic:

```text
today_close <= previous_close * (1 + buy_condition_percent / 100)
```

If open position count is greater than or equal to the split count for the current mode, no new buy is allowed.

Position amount:

```text
capital / split_count
```

Quantity:

```text
floor(position_amount / close_price)
```

If quantity is zero, no buy is allowed.

### Sell Rule

Each position is evaluated independently.

Return percent:

```text
(current_price - buy_price) / buy_price * 100
```

Sell when either:

- return percent is greater than or equal to sell threshold percent
- holding days are greater than or equal to max holding period

The sell signal includes a reason.

### Fees and Slippage

Fees apply to both buy and sell transactions.

The first version stores slippage settings and applies them in the execution simulator and signal execution defaults. Manual fills can override price and quantity.

## Live Trading Support

The platform does not place brokerage orders.

Daily workflow:

1. User opens the dashboard.
2. The system calculates today buy/sell signals using the selected strategy config.
3. User clicks signal execution.
4. The system pre-fills quantity, price, fee, and reason.
5. User confirms or edits the fill.
6. The live portfolio, positions, and trades are updated.

If real execution differs because of partial fills, missed fills, price differences, or mistakes, the user can correct records manually.

## Backtest Engine

The backtest engine is strategy-agnostic. It receives:

- strategy instance
- strategy settings snapshot
- normalized market data
- initial capital
- fee and slippage settings
- date range

Daily loop:

1. Load data for current date.
2. Update open position valuation.
3. Evaluate sell signals per position and execute sells.
4. Evaluate buy signal and execute buy if allowed.
5. Update capital if the configured schedule is due.
6. Store daily snapshot.
7. After the loop, calculate summary metrics.

Backtest storage is separate from live trades and live positions.

## API Design

Initial REST endpoints:

```text
GET    /api/strategies
GET    /api/strategies/{type}/schema
POST   /api/strategy-configs
GET    /api/strategy-configs
GET    /api/strategy-configs/{id}
PUT    /api/strategy-configs/{id}
GET    /api/dashboard/{config_id}
POST   /api/signals/{config_id}/execute
POST   /api/trades/manual
GET    /api/positions/{config_id}
GET    /api/trades/{config_id}
POST   /api/backtests
GET    /api/backtests/{run_id}
GET    /api/backtests/{run_id}/daily.csv
GET    /api/backtests/{run_id}/trades.csv
GET    /api/backtests/{run_id}/summary.csv
```

## Frontend Screens

### Dashboard

Shows:

- current mode
- capital
- cash
- total asset value
- realized PnL
- unrealized PnL
- cumulative fees
- cumulative return
- today buy signal
- today sell signals
- open positions table
- recent trades table

Includes an action to execute signals with editable fill defaults.

### Backtest

Inputs:

- strategy config
- start date
- end date

Outputs:

- CAGR
- MDD
- final asset value
- total return
- win rate
- total trades
- average holding period
- cumulative fees
- asset curve
- MDD chart
- trade markers
- CSV downloads

### Strategy Settings

Renders common settings and the selected strategy-specific schema.

### Trades and Positions

Allows inspection and manual correction of live trade and position records.

## Error Handling

API errors must be specific and actionable.

Expected error categories:

- market data unavailable for symbol and date range
- market data provider failure
- invalid strategy settings
- insufficient cash
- calculated quantity is zero
- split count limit reached
- no previous close available for buy rule
- backtest run failed

Backtest failures are persisted on the run with `failed` status and an error message.

## Testing

Backend tests:

- Dynamic Wave buy rule
- Dynamic Wave sell rule
- split count limit
- position size calculation
- fee calculation
- capital update with PCR/LCR
- trading-day and calendar capital update schedules
- backtest loop with fixed OHLCV fixtures
- repository tests against SQLite test database
- FastAPI endpoint tests with TestClient

Frontend checks:

- TypeScript type checking
- production build
- critical component tests if the test stack is included during implementation

Network-dependent tests are avoided. Market data provider behavior should be tested through fixtures or mocked providers.

## Execution Environment

Provide:

- backend dependency file
- frontend package setup
- Dockerfile for backend
- Dockerfile for frontend
- `docker-compose.yml`
- SQLite volume
- README with local and Docker execution instructions
- seed data for default owner and sample Dynamic Wave config

## Open Design Decisions Resolved

- First version scope: full skeleton plus Dynamic Wave core flow.
- User model: personal single-user default owner, with owner IDs for future multi-user support.
- Data provider: FinanceDataReader plus SQLite cache by default.
- Live execution: generated signals can be virtually executed, then manually corrected.
- Capital update schedule: support both trading-day and calendar schedules.
- Architecture: modular monolith backend with separated frontend.
