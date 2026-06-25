# Daily Trading Plan, Chart, and RSI Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an exact weekly QQQ RSI mode recommendation, manually confirmed live mode, next-session LOC price and quantity, and an operational investment chart to the existing quant platform.

**Architecture:** Keep RSI and LOC calculations as deterministic strategy-engine functions. Persist confirmed/recommended mode state behind repositories, expose calculation results through focused FastAPI services and DTOs, and let React render typed backend results without duplicating finance logic. Reuse the same mode policy and LOC operation from the backtest engine.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, SQLite, pytest, React 18, TypeScript, Vite, Lightweight Charts 4.

---

## File Map

**Backend strategy and domain**

- Create `backend/app/strategy_engine/weekly_rsi.py`: weekly resampling, SMA RSI(14), S1-S3/A1-A3 resolver.
- Create `backend/app/strategy_engine/loc.py`: pure LOC plan calculation shared by live and backtest paths.
- Modify `backend/app/strategy_engine/context.py`: carry an explicit effective mode.
- Modify `backend/app/strategy_engine/dynamic_wave.py`: use effective mode and shared LOC operation.
- Modify `backend/app/domain/enums.py`: mode source and backtest mode policy enums.
- Modify `backend/app/domain/models.py`: mode state and immutable recommendation history models.

**Backend persistence and application**

- Create `backend/app/infrastructure/repositories/modes.py`: mode state/history persistence.
- Modify `backend/app/infrastructure/repositories/trades.py`: date-range query for chart markers.
- Create `backend/app/services/mode_service.py`: recommendation and confirmation workflows.
- Create `backend/app/services/daily_plan_service.py`: next-session LOC plan orchestration.
- Create `backend/app/services/chart_service.py`: typed OHLCV, RSI, guide, and marker data.
- Create `backend/app/services/market_refresh_service.py`: explicit investment/RSI symbol refresh.
- Create `backend/app/dto/trading_plan.py`: request and response schemas for new APIs.
- Create `backend/app/api/routes_trading_plan.py`: mode, plan, chart, and refresh routes.
- Modify `backend/app/main.py`: register the new router.
- Modify `backend/app/services/strategy_config_service.py`: initialize Safe mode state with new configs.

**Backtest**

- Modify `backend/app/backtest_engine/simulator.py`: snapshot effective mode and rule code.
- Modify `backend/app/backtest_engine/engine.py`: resolve weekly/fixed mode without lookahead and use LOC close fills.
- Modify `backend/app/services/backtest_service.py`: fetch QQQ initialization history and store mode policy.
- Modify `backend/app/dto/backtests.py`: expose mode policy and daily mode metadata.

**Frontend**

- Modify `frontend/src/types/api.ts`: typed plan, mode, and chart contracts.
- Modify `frontend/src/api/client.ts`: support bodyless POST requests.
- Create `frontend/src/api/tradingPlan.ts`: new endpoint client functions.
- Create `frontend/src/components/ModeControl.tsx`: confirmed/recommended mode controls.
- Create `frontend/src/components/DailyPlanPanel.tsx`: Korean LOC instruction and blocking reason.
- Create `frontend/src/components/MarketChart.tsx`: candlestick, volume, LOC, and trade markers.
- Create `frontend/src/components/RsiChart.tsx`: weekly RSI guides and transition markers.
- Modify `frontend/src/pages/DashboardPage.tsx`: integrated operational dashboard.
- Modify `frontend/src/styles.css`: stable responsive chart and control layout.

## Task 1: Exact Weekly RSI Resolver

**Files:**
- Create: `backend/app/strategy_engine/weekly_rsi.py`
- Create: `backend/tests/test_weekly_rsi.py`
- Create: `backend/tests/fixtures/weekly_mode_transitions.csv`

- [ ] **Step 1: Write failing formula, boundary, and regression tests**

```python
def test_report_transition_is_aggressive_a1() -> None:
    result = resolve_rsi_transition(Decimal("49.3589779596"), Decimal("53.5996753027"), StrategyMode.SAFE)
    assert result.mode is StrategyMode.AGGRESSIVE
    assert result.rule_code == "A1"

@pytest.mark.parametrize(
    ("previous", "current", "prior_mode", "expected_mode", "rule"),
    [
        ("65", "64", StrategyMode.AGGRESSIVE, StrategyMode.SAFE, "S1"),
        ("45", "44", StrategyMode.AGGRESSIVE, StrategyMode.SAFE, "S2"),
        ("50", "49", StrategyMode.AGGRESSIVE, StrategyMode.SAFE, "S3"),
        ("50", "51", StrategyMode.SAFE, StrategyMode.AGGRESSIVE, "A1"),
        ("55", "56", StrategyMode.SAFE, StrategyMode.AGGRESSIVE, "A2"),
        ("35", "36", StrategyMode.SAFE, StrategyMode.AGGRESSIVE, "A3"),
    ],
)
def test_transition_boundaries(previous, current, prior_mode, expected_mode, rule) -> None:
    result = resolve_rsi_transition(Decimal(previous), Decimal(current), prior_mode)
    assert (result.mode, result.rule_code) == (expected_mode, rule)
```

The CSV contains the supplied workbook's effective week and expected mode columns only, covering all 156 weeks from 2023 through 2025. The test constructs daily/weekly close fixtures already verified during discovery and asserts zero mode mismatches.

- [ ] **Step 2: Run tests and verify the resolver is missing**

Run: `cd backend; uv run pytest tests/test_weekly_rsi.py -q`

Expected: FAIL during import because `app.strategy_engine.weekly_rsi` does not exist.

- [ ] **Step 3: Implement deterministic weekly RSI and transition rules**

```python
@dataclass(frozen=True)
class RsiTransition:
    mode: StrategyMode
    rule_code: str | None

def resolve_rsi_transition(previous: Decimal, current: Decimal, prior: StrategyMode) -> RsiTransition:
    if previous >= Decimal("65") and current < previous:
        return RsiTransition(StrategyMode.SAFE, "S1")
    if Decimal("40") <= previous <= Decimal("50") and current < previous:
        return RsiTransition(StrategyMode.SAFE, "S2")
    if previous >= Decimal("50") and current < Decimal("50"):
        return RsiTransition(StrategyMode.SAFE, "S3")
    if previous <= Decimal("50") and current > Decimal("50"):
        return RsiTransition(StrategyMode.AGGRESSIVE, "A1")
    if Decimal("50") <= previous <= Decimal("60") and current > previous:
        return RsiTransition(StrategyMode.AGGRESSIVE, "A2")
    if previous <= Decimal("35") and current > previous:
        return RsiTransition(StrategyMode.AGGRESSIVE, "A3")
    return RsiTransition(prior, None)
```

Implement Friday-ending weeks by grouping each daily date by its following Friday and selecting the last available close. Calculate each RSI point from 14 gains/losses with simple arithmetic means; when average loss is zero, return 100, and when both averages are zero, return 50. A recommendation uses only completed weeks and is effective on the Monday after the current week-ending Friday.

- [ ] **Step 4: Run focused tests**

Run: `cd backend; uv run pytest tests/test_weekly_rsi.py -q`

Expected: all formula, holiday-week, boundary, no-change, effective-week, and 156-week regression tests PASS.

- [ ] **Step 5: Commit**

```text
git add backend/app/strategy_engine/weekly_rsi.py backend/tests/test_weekly_rsi.py backend/tests/fixtures/weekly_mode_transitions.csv
git commit -m "feat: add exact weekly RSI mode resolver"
```

## Task 2: Shared LOC Calculation and Explicit Strategy Mode

**Files:**
- Create: `backend/app/strategy_engine/loc.py`
- Modify: `backend/app/strategy_engine/context.py`
- Modify: `backend/app/strategy_engine/dynamic_wave.py`
- Modify: `backend/tests/test_dynamic_wave_strategy.py`
- Create: `backend/tests/test_loc.py`

- [ ] **Step 1: Write failing LOC and effective-mode tests**

```python
def test_loc_uses_previous_close_capital_and_confirmed_mode() -> None:
    result = calculate_loc_plan(
        previous_close=Decimal("100"),
        capital=Decimal("1000"),
        cash=Decimal("1000"),
        fee_rate=Decimal("0.1"),
        split_count=5,
        buy_threshold_percent=Decimal("5"),
        open_position_count=0,
    )
    assert result.limit_price == Decimal("105.000000")
    assert result.allocation == Decimal("200.000000")
    assert result.quantity == 1
    assert result.estimated_fee == Decimal("0.105000")
    assert result.available is True

def test_dynamic_wave_get_mode_uses_context_effective_mode() -> None:
    context = make_context(effective_mode=StrategyMode.AGGRESSIVE)
    assert DynamicWaveStrategy().get_mode(context) is StrategyMode.AGGRESSIVE
```

- [ ] **Step 2: Run tests and verify failure**

Run: `cd backend; uv run pytest tests/test_loc.py tests/test_dynamic_wave_strategy.py -q`

Expected: FAIL because `calculate_loc_plan` and `effective_mode` are missing.

- [ ] **Step 3: Implement the pure LOC result and wire effective mode**

```python
@dataclass(frozen=True)
class AodPlan:
    limit_price: Decimal
    allocation: Decimal
    quantity: int
    estimated_fee: Decimal
    required_cash: Decimal
    available: bool
    blocking_reason: str | None

limit_price = quantize(previous_close * (Decimal("1") + buy_threshold_percent / Decimal("100")))
allocation = quantize(capital / Decimal(split_count))
quantity = int((allocation / limit_price).to_integral_value(rounding=ROUND_DOWN))
estimated_fee = quantize(limit_price * quantity * fee_rate / Decimal("100"))
required_cash = quantize(limit_price * quantity + estimated_fee)
```

Apply blocking reasons in this precedence: `split_limit_reached`, `quantity_zero`, `insufficient_cash`. Add `effective_mode: StrategyMode = StrategyMode.SAFE` to `StrategyContext`; make `DynamicWaveStrategy.get_mode()` return it. `should_buy()` compares the session close to the shared LOC limit, while `calculate_position_size()` uses the shared allocation and limit basis.

- [ ] **Step 4: Run focused tests**

Run: `cd backend; uv run pytest tests/test_loc.py tests/test_dynamic_wave_strategy.py -q`

Expected: PASS, including fee, zero quantity, insufficient Cash, and split limit.

- [ ] **Step 5: Commit**

```text
git add backend/app/strategy_engine/loc.py backend/app/strategy_engine/context.py backend/app/strategy_engine/dynamic_wave.py backend/tests/test_loc.py backend/tests/test_dynamic_wave_strategy.py
git commit -m "refactor: share LOC calculation and explicit mode"
```

## Task 3: Persist Confirmed and Recommended Modes

**Files:**
- Modify: `backend/app/domain/enums.py`
- Modify: `backend/app/domain/models.py`
- Create: `backend/app/infrastructure/repositories/modes.py`
- Modify: `backend/app/services/strategy_config_service.py`
- Create: `backend/tests/test_mode_repository.py`
- Modify: `backend/tests/test_services.py`

- [ ] **Step 1: Write failing repository and initialization tests**

```python
def test_new_config_starts_with_visible_safe_confirmation(session: Session) -> None:
    config = create_config(session)
    state = ModeStateRepository(session).get(config.id)
    assert state is not None
    assert state.confirmed_mode is StrategyMode.SAFE
    assert state.confirmed_source is ModeConfirmationSource.MANUAL

def test_recommendation_is_idempotent_per_effective_week(session: Session) -> None:
    repo = ModeRecommendationRepository(session)
    first = repo.upsert(make_recommendation(date(2026, 6, 22), "A1"))
    second = repo.upsert(make_recommendation(date(2026, 6, 22), "A1"))
    assert first.id == second.id
```

- [ ] **Step 2: Run tests and verify missing models**

Run: `cd backend; uv run pytest tests/test_mode_repository.py tests/test_services.py -q`

Expected: FAIL importing `StrategyModeState` and repository classes.

- [ ] **Step 3: Add models and repositories**

`StrategyModeState` uses `strategy_config_id` as a foreign-key primary key and stores confirmed mode/source/time plus nullable current recommendation metadata. `ModeRecommendation` has a unique constraint on `(strategy_config_id, effective_week)` and stores data-as-of date, previous/current RSI, recommended mode, rule code, and calculation time. Add repository methods `get`, `get_or_create_safe`, `save`, `upsert`, `get_current`, and `list_by_config` ordered newest first.

Use these enum values:

```python
class ModeConfirmationSource(StrEnum):
    MANUAL = "manual"
    RECOMMENDATION_APPLIED = "recommendation_applied"

class BacktestModePolicy(StrEnum):
    WEEKLY_RSI = "weekly_rsi"
    FIXED_SAFE = "fixed_safe"
    FIXED_AGGRESSIVE = "fixed_aggressive"
```

Initialize mode state in the same transaction that creates a strategy config and portfolio.

- [ ] **Step 4: Run repository and service tests**

Run: `cd backend; uv run pytest tests/test_mode_repository.py tests/test_services.py -q`

Expected: PASS with SQLite foreign keys and unique-key idempotency covered.

- [ ] **Step 5: Commit**

```text
git add backend/app/domain backend/app/infrastructure/repositories/modes.py backend/app/services/strategy_config_service.py backend/tests/test_mode_repository.py backend/tests/test_services.py
git commit -m "feat: persist strategy mode state and history"
```

## Task 4: Mode Recommendation and Confirmation APIs

**Files:**
- Create: `backend/app/services/mode_service.py`
- Create: `backend/app/dto/trading_plan.py`
- Create: `backend/app/api/routes_trading_plan.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_mode_service.py`
- Create: `backend/tests/test_api_trading_plan.py`

- [ ] **Step 1: Write failing service and API tests**

```python
def test_new_recommendation_does_not_change_confirmed_mode(service) -> None:
    result = service.recalculate(config_id=1, as_of=date(2026, 6, 19))
    assert result.recommended_mode is StrategyMode.AGGRESSIVE
    assert service.get_state(1).confirmed_mode is StrategyMode.SAFE

def test_apply_recommendation_changes_confirmed_mode(api_client) -> None:
    response = api_client.put(
        "/api/strategy-configs/1/confirmed-mode",
        json={"action": "apply_recommendation"},
    )
    assert response.status_code == 200
    assert response.json()["confirmed_mode"] == "aggressive"
    assert response.json()["confirmed_source"] == "recommendation_applied"
```

Also test direct `{ "action": "set", "mode": "safe" }`, no-current-recommendation validation, fewer than 15 weekly closes, missing config 404, and history ordering.

- [ ] **Step 2: Run tests and verify missing service/router**

Run: `cd backend; uv run pytest tests/test_mode_service.py tests/test_api_trading_plan.py -q`

Expected: FAIL because mode service and endpoints do not exist.

- [ ] **Step 3: Implement mode workflows and typed DTOs**

`ModeRecommendationService.recalculate(config_id, as_of)` loads the configured `mode_rsi_symbol`, resolves completed weekly data, persists one history row, and updates only recommendation fields on mode state. `ModeConfirmationService.confirm(config_id, mode)` records source `manual`; `apply_recommendation(config_id)` copies the current recommendation and records source `recommendation_applied`.

Expose:

```text
GET /api/strategy-configs/{id}/mode-recommendation
PUT /api/strategy-configs/{id}/confirmed-mode
GET /api/strategy-configs/{id}/mode-recommendations
```

Responses include `confirmed_mode`, `confirmed_source`, `recommended_mode`, `differs`, `effective_week`, `data_as_of`, `previous_rsi`, `current_rsi`, and `rule_code`. Map missing config to 404 and invalid apply action to 422.

- [ ] **Step 4: Run mode tests**

Run: `cd backend; uv run pytest tests/test_mode_service.py tests/test_api_trading_plan.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```text
git add backend/app/services/mode_service.py backend/app/dto/trading_plan.py backend/app/api/routes_trading_plan.py backend/app/main.py backend/tests/test_mode_service.py backend/tests/test_api_trading_plan.py
git commit -m "feat: expose RSI recommendation and mode confirmation"
```

## Task 5: Daily Plan, Chart, and Explicit Refresh APIs

**Files:**
- Create: `backend/app/services/daily_plan_service.py`
- Create: `backend/app/services/chart_service.py`
- Create: `backend/app/services/market_refresh_service.py`
- Modify: `backend/app/infrastructure/repositories/trades.py`
- Modify: `backend/app/infrastructure/repositories/market_data.py`
- Modify: `backend/app/dto/trading_plan.py`
- Modify: `backend/app/api/routes_trading_plan.py`
- Create: `backend/tests/test_daily_plan_service.py`
- Create: `backend/tests/test_chart_service.py`
- Modify: `backend/tests/test_api_trading_plan.py`

- [ ] **Step 1: Write failing plan, chart, and refresh tests**

```python
def test_daily_plan_uses_last_completed_close_and_confirmed_mode(service) -> None:
    plan = service.get(config_id=1, today=date(2026, 6, 20))
    assert plan.market_data_as_of == date(2026, 6, 19)
    assert plan.confirmed_mode is StrategyMode.SAFE
    assert plan.loc_limit_price == Decimal("103.000000")
    assert plan.quantity == 1

def test_chart_returns_sorted_ohlcv_loc_and_markers(service) -> None:
    chart = service.get(config_id=1, range_key="6m", today=date(2026, 6, 20))
    assert [row.date for row in chart.candles] == sorted(row.date for row in chart.candles)
    assert chart.loc.value == Decimal("103.000000")
    assert {marker.kind for marker in chart.trade_markers} == {"buy", "sell"}
    assert chart.rsi.guides == [Decimal("35"), Decimal("40"), Decimal("50"), Decimal("60"), Decimal("65")]
```

Test all range keys, stale `data_as_of`, holiday next-session labeling, no previous close, refresh of both configured symbols, and provider failure preserving cached responses.

- [ ] **Step 2: Run tests and verify missing services**

Run: `cd backend; uv run pytest tests/test_daily_plan_service.py tests/test_chart_service.py tests/test_api_trading_plan.py -q`

Expected: FAIL importing daily plan and chart services.

- [ ] **Step 3: Implement services and endpoints**

`DailyTradingPlanService` loads config, portfolio, open positions, mode state, and the latest cached investment close not after today, then calls `calculate_loc_plan`. Return `buy_available=False` with a stable blocking code when any dependency is unavailable.

`ChartService` maps range keys to 31, 93, 186, and 366 calendar days. It returns sorted daily candles and volume, one current LOC line, persisted trades in range, weekly RSI points, numeric guides `[35, 40, 50, 60, 65]`, and recommendation-history transition markers.

`MarketRefreshService` explicitly fetches at least 400 calendar days for both the investment symbol and `mode_rsi_symbol`, upserts them, recalculates recommendation, and returns each symbol's last data date. It never changes confirmed mode.

Expose:

```text
POST /api/strategy-configs/{id}/market-data/refresh
GET  /api/strategy-configs/{id}/daily-plan
GET  /api/strategy-configs/{id}/chart?range=1m|3m|6m|1y
```

- [ ] **Step 4: Run focused and existing API tests**

Run: `cd backend; uv run pytest tests/test_daily_plan_service.py tests/test_chart_service.py tests/test_api_trading_plan.py tests/test_api_dashboard.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```text
git add backend/app/services backend/app/infrastructure/repositories backend/app/dto/trading_plan.py backend/app/api/routes_trading_plan.py backend/tests/test_daily_plan_service.py backend/tests/test_chart_service.py backend/tests/test_api_trading_plan.py
git commit -m "feat: add daily LOC plan chart and market refresh APIs"
```

## Task 6: Backtest Mode Policy and LOC Fill Reuse

**Files:**
- Modify: `backend/app/backtest_engine/simulator.py`
- Modify: `backend/app/backtest_engine/engine.py`
- Modify: `backend/app/services/backtest_service.py`
- Modify: `backend/app/dto/backtests.py`
- Modify: `backend/tests/test_backtest_engine.py`
- Modify: `backend/tests/test_api_backtests.py`

- [ ] **Step 1: Write failing no-lookahead and policy tests**

```python
def test_weekly_rsi_mode_becomes_effective_next_week() -> None:
    result = run_mode_fixture(policy="weekly_rsi")
    assert result.daily_snapshots[friday_index].mode == "safe"
    assert result.daily_snapshots[monday_index].mode == "aggressive"
    assert result.daily_snapshots[monday_index].mode_rule_code == "A1"

def test_loc_buy_fills_at_close_when_close_is_within_limit() -> None:
    result = run_gap_fixture(previous_close=Decimal("100"), low=Decimal("90"), close=Decimal("104"))
    buy = next(trade for trade in result.trades if trade.side == "BUY")
    assert buy.price == Decimal("104.000000")
```

Also test `fixed_safe`, `fixed_aggressive`, a daily low below the LOC limit with a close above it (no fill), slippage applied after the closing fill price, and mode/rule persistence in API snapshots.

- [ ] **Step 2: Run tests and verify policy support is absent**

Run: `cd backend; uv run pytest tests/test_backtest_engine.py tests/test_api_backtests.py -q`

Expected: FAIL because snapshots do not expose mode metadata and current buys use current close.

- [ ] **Step 3: Implement backtest policy and LOC execution**

Add `mode` and nullable `mode_rule_code` to `DailySnapshot`. `BacktestEngine.run()` accepts a mode policy and RSI-symbol prices. For `weekly_rsi`, precompute recommendations from data completed before each effective week; fixed policies return their fixed mode. Build every `StrategyContext` with that day's effective mode.

For each investment session, calculate the LOC threshold from the preceding close. A buy is eligible only when `daily.close <= limit_price`; use `daily.close` as the unadjusted fill, then apply configured buy slippage. Daily open, high, and low do not trigger the order. Quantity remains based on the LOC limit price so live instructions and simulations share allocation logic.

Fetch enough pre-start QQQ data to initialize RSI, exclude post-decision data, and store `mode_policy` in `strategy_config_snapshot_json`.

- [ ] **Step 4: Run all backend tests**

Run: `cd backend; uv run pytest -q`

Expected: all backend tests PASS.

- [ ] **Step 5: Commit**

```text
git add backend/app/backtest_engine backend/app/services/backtest_service.py backend/app/dto/backtests.py backend/tests/test_backtest_engine.py backend/tests/test_api_backtests.py
git commit -m "feat: reuse RSI modes and LOC limits in backtests"
```

## Task 7: Typed Integrated Dashboard

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/api/tradingPlan.ts`
- Create: `frontend/src/components/ModeControl.tsx`
- Create: `frontend/src/components/DailyPlanPanel.tsx`
- Create: `frontend/src/components/MarketChart.tsx`
- Create: `frontend/src/components/RsiChart.tsx`
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Add exact TypeScript API contracts and client calls**

```typescript
export type StrategyMode = "safe" | "aggressive";
export type ChartRange = "1m" | "3m" | "6m" | "1y";

export interface ModeRecommendation {
  confirmed_mode: StrategyMode;
  confirmed_source: "manual" | "recommendation_applied";
  recommended_mode: StrategyMode | null;
  differs: boolean;
  effective_week: ISODate | null;
  data_as_of: ISODate | null;
  previous_rsi: DecimalString | null;
  current_rsi: DecimalString | null;
  rule_code: string | null;
}
```

Define complete interfaces for daily plan, candles, volume, LOC line, trade markers, weekly RSI points, mode markers, and chart response matching backend DTO field names. Add `getDailyPlan`, `getChart`, `getModeRecommendation`, `setConfirmedMode`, and `refreshMarketData` functions.

- [ ] **Step 2: Build and verify type errors identify missing components**

Run: `cd frontend; npm run build`

Expected: FAIL until the new component imports and response handling are implemented.

- [ ] **Step 3: Implement operational controls and charts**

`ModeControl` renders a Safe/Aggressive segmented control, recommendation values/rule, Apply button, and a Korean mismatch warning. Buttons remain stable width and expose `aria-pressed`.

`DailyPlanPanel` renders LOC limit, quantity, previous close, threshold, Capital, split count, allocation, fee, required Cash, and translated blocking reason. It never recalculates a value in TypeScript.

`MarketChart` creates a candlestick series, volume histogram, dashed LOC price line, and buy/sell markers. `RsiChart` creates a weekly line, horizontal guides at 35/40/50/60/65, and Safe/Aggressive transition markers. Both observe container width and remove chart/observer on cleanup.

`DashboardPage` loads dashboard, plan, chart, mode, and trades for the selected configuration; defaults to `6m`; reloads after confirmation; and invokes explicit refresh from the existing refresh button. Replace any mojibake visible in this page and the touched API error messages with Korean UTF-8 text.

- [ ] **Step 4: Build frontend**

Run: `cd frontend; npm run build`

Expected: TypeScript and Vite build complete successfully.

- [ ] **Step 5: Commit**

```text
git add frontend/src/types/api.ts frontend/src/api frontend/src/components frontend/src/pages/DashboardPage.tsx frontend/src/styles.css
git commit -m "feat: add Korean daily plan and RSI chart dashboard"
```

## Task 8: End-to-End Verification and Documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document the operating flow**

Add Korean README instructions covering explicit market refresh, recommendation interpretation, manual mode confirmation, LOC order placement, virtual fill recording, manual correction, chart ranges, and the three backtest mode policies. State that the system does not submit brokerage orders.

- [ ] **Step 2: Run static and automated verification**

Run: `cd backend; uv run ruff check app tests`

Expected: no lint errors.

Run: `cd backend; uv run pytest -q`

Expected: all backend tests PASS.

Run: `cd frontend; npm run build`

Expected: build succeeds.

- [ ] **Step 3: Start both development servers**

Run backend: `cd backend; uv run uvicorn app.main:app --host 127.0.0.1 --port 8000`

Run frontend: `cd frontend; npm run dev -- --host 127.0.0.1 --port 5173`

Expected: health endpoint returns 200 and Vite serves the dashboard.

- [ ] **Step 4: Verify in the in-app browser**

At desktop 1440x900 and mobile 390x844, verify: no overlap, Korean text is readable, candlestick/volume/RSI canvases contain non-background pixels, range switching changes data, manual mode survives refresh, Apply recommendation updates confirmed mode, and browser console has no errors.

- [ ] **Step 5: Commit documentation and final fixes**

```text
git add README.md backend frontend
git commit -m "docs: explain daily trading support workflow"
```
