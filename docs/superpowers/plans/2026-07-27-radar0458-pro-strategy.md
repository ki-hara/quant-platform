# Radar0458 Pro Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an independent SOXL-only Radar0458 Pro strategy and a read-only integrated strategy order workspace without changing Dynamic Wave behavior.

**Architecture:** Keep `DynamicWaveStrategy` and its calculation path intact. Add a pure Radar preset/tier planner, route Radar configurations through strategy-specific orchestration branches, and persist nullable Radar position snapshots. Build integrated orders by reading each included strategy's existing daily plan and sell signals, then aggregate and net them without mutating strategy state.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, SQLite migrations, pytest, React, TypeScript, Vite.

## Global Constraints

- `radar0458_pro` is independent from `dynamic_wave`.
- Radar0458 Pro supports SOXL only and manual Pro1/Pro2/Pro3 selection.
- Dynamic Wave RSI, safe/aggressive mode, snapshots, Capital updates, plans, and backtests retain existing behavior.
- Pro settings are fixed presets; configuration changes apply to the next cycle only.
- Integrated-order inclusion affects only the `전략 통합 주문` page.
- The integrated page is read-only and never records fills or changes positions.
- Every implementation task ends in a separate commit. Do not push.
- Follow RED-GREEN-REFACTOR for new behavior.

---

### Task 1: Radar Preset and Tier Domain

**Files:**
- Create: `backend/app/strategy_engine/radar0458_pro.py`
- Modify: `backend/app/strategy_engine/registry.py`
- Modify: `backend/app/services/strategy_config_service.py`
- Test: `backend/tests/test_radar0458_pro_strategy.py`
- Test: `backend/tests/test_services.py`

**Interfaces:**
- Produces `RadarPreset`, `RadarTierPlan`, `RADAR_PRESETS`, `get_radar_preset()`, `next_radar_tier()`, and `build_radar_buy_plan()`.
- Registers `Radar0458ProStrategy` with type `radar0458_pro`.
- The strategy schema exposes `pro_profile` with `pro1`, `pro2`, and `pro3`; default is `pro1`.

- [ ] **Step 1: Write failing preset and tier tests**

Assert the exact tier ratios and rules:

```python
assert RADAR_PRESETS["pro1"].tier_ratios == (
    Decimal("0.05"), Decimal("0.10"), Decimal("0.15"),
    Decimal("0.20"), Decimal("0.25"), Decimal("0.25"),
)
assert RADAR_PRESETS["pro2"].sell_threshold_percent == Decimal("1.50")
assert RADAR_PRESETS["pro3"].tier_ratios == (Decimal("1") / Decimal("6"),) * 6
assert next_radar_tier({1, 3, 4}) == 2
assert next_radar_tier({1, 2, 3, 4, 5, 6}) == 7
assert next_radar_tier({1, 2, 3, 4, 5, 6, 7}) is None
```

Assert buy limit rounding down to USD 0.01 and quantity uses `floor(allocation / limit_price)`.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
cd backend
uv run pytest tests/test_radar0458_pro_strategy.py tests/test_services.py -q
```

Expected: import or registry assertions fail because Radar classes do not exist.

- [ ] **Step 3: Implement the pure Radar domain**

Use immutable dataclasses:

```python
@dataclass(frozen=True)
class RadarPreset:
    code: str
    tier_ratios: tuple[Decimal, ...]
    buy_threshold_percent: Decimal
    sell_threshold_percent: Decimal
    max_holding_days: int

@dataclass(frozen=True)
class RadarTierPlan:
    tier: int | None
    profile: str
    cycle_capital: Decimal
    limit_price: Decimal
    allocation: Decimal
    quantity: int
    blocking_reason: str | None
```

`build_radar_buy_plan()` accepts previous close, cycle Capital, available cash, occupied start-of-day tiers, and profile. Tier 7 uses available cash; regular tiers use the preset ratio.

`Radar0458ProStrategy` supplies registry metadata and settings schema. Its generic mode methods must not be used by Radar orchestration and should not contain Dynamic Wave calculations.

- [ ] **Step 4: Validate Radar configuration**

In `StrategyConfigService`, reject a Radar configuration unless:

```python
symbol.upper() == "SOXL"
settings_json["pro_profile"] in {"pro1", "pro2", "pro3"}
```

Do not alter Dynamic Wave validation behavior.

- [ ] **Step 5: Run focused tests and commit**

Run the Task 1 test command and commit:

```powershell
git add backend/app/strategy_engine backend/app/services/strategy_config_service.py backend/tests
git commit -m "feat: add radar0458 pro strategy domain"
```

---

### Task 2: Radar Position Snapshots and Live Daily Plan

**Files:**
- Modify: `backend/app/domain/models.py`
- Modify: `backend/app/db/migrations.py`
- Modify: `backend/app/infrastructure/repositories/portfolios.py`
- Modify: `backend/app/dto/dashboard.py`
- Modify: `backend/app/dto/trading_plan.py`
- Modify: `backend/app/services/daily_plan_service.py`
- Modify: `backend/app/services/dashboard_service.py`
- Modify: `backend/app/services/manual_trade_service.py`
- Modify: `backend/app/services/loc_order_service.py`
- Modify: `backend/app/api/routes_trades.py`
- Test: `backend/tests/test_migrations.py`
- Test: `backend/tests/test_daily_plan_service.py`
- Test: `backend/tests/test_api_trading_plan.py`
- Test: `backend/tests/test_api_trades.py`

**Interfaces:**
- Adds nullable Position fields: `radar_tier`, `radar_profile`, `radar_cycle_id`, and `radar_cycle_capital`.
- Adds nullable daily-plan fields: `strategy_type`, `radar_profile`, `radar_tier`, and `radar_cycle_capital`.
- Buy-order and manual-buy requests accept the same nullable Radar metadata.

- [ ] **Step 1: Write failing migration and plan tests**

Test migration version 4 adds:

```text
positions.radar_tier INTEGER
positions.radar_profile VARCHAR(16)
positions.radar_cycle_id VARCHAR(64)
positions.radar_cycle_capital NUMERIC(18, 6)
```

Test a Radar daily plan with occupied tiers `{1, 3, 4}` selects tier 2 and uses the active positions' profile and cycle Capital even after settings and portfolio Capital change.

Test no open positions starts a new cycle from current `settings_json["pro_profile"]` and `portfolio.capital`.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
cd backend
uv run pytest tests/test_migrations.py tests/test_daily_plan_service.py tests/test_api_trading_plan.py -q
```

- [ ] **Step 3: Add nullable persistence and DTO fields**

Extend `PositionRepository.create_open()` and `create_pending()` with keyword-only nullable Radar metadata. Include fields in `PositionDto` and frontend-compatible daily-plan responses.

Generate cycle IDs as stable UUID strings only when starting a new Radar cycle. Existing open positions supply the active cycle ID, profile, and cycle Capital.

- [ ] **Step 4: Add Radar daily-plan orchestration**

At the start of `DailyPlanService.get_daily_plan()`:

```python
if config.strategy_type == "radar0458_pro":
    return self._get_radar_daily_plan(config, portfolio, open_positions, order_date)
```

The Dynamic Wave body remains semantically unchanged.

Radar planning:

- uses previous confirmed close;
- treats pending and open positions as occupied tiers;
- blocks with `radar_position_snapshot_missing` if a Radar position lacks required metadata;
- uses the active cycle snapshot while any position exists;
- returns no buy when all seven tiers are occupied.

- [ ] **Step 5: Snapshot Radar metadata on order creation and fill**

Extend buy-order creation and LOC-order fill paths so pending and open positions retain tier, profile, cycle ID, cycle Capital, sell threshold, sell limit, and maximum holding days. Radar sell limits are ordinary USD 0.01 rounding.

When a Radar sell realizes profit or loss, add 100% of that realized P/L to `portfolio.capital`. Existing Dynamic Wave PCR/LCR behavior remains untouched.

- [ ] **Step 6: Add Radar dashboard signal branch**

Radar dashboard buy information comes from the Radar daily plan. Sell signals use each position's persisted sell threshold and maximum holding days. Return Radar metadata for display and skip Dynamic Wave automatic Capital-cycle updates for Radar configurations.

- [ ] **Step 7: Run focused and Dynamic Wave regression tests**

Run:

```powershell
cd backend
uv run pytest tests/test_migrations.py tests/test_daily_plan_service.py tests/test_api_trading_plan.py tests/test_api_trades.py tests/test_dashboard_service.py tests/test_dynamic_wave_strategy.py -q
```

Commit:

```powershell
git add backend/app backend/tests
git commit -m "feat: add radar0458 pro live cycle planning"
```

---

### Task 3: Radar Backtest

**Files:**
- Modify: `backend/app/backtest_engine/engine.py`
- Modify: `backend/app/services/backtest_service.py`
- Modify: `backend/app/dto/backtests.py`
- Modify: `backend/app/domain/models.py`
- Modify: `frontend/src/types/api.ts`
- Test: `backend/tests/test_backtest_engine.py`
- Test: `backend/tests/test_api_backtests.py`
- Test: `backend/tests/fixtures/radar0458_pro_2026_tiers.json`

**Interfaces:**
- Radar backtests read `pro_profile` from the selected strategy configuration.
- Backtest open positions carry Radar tier/profile/cycle snapshots in memory.
- Dynamic Wave continues using `mode_policy` and `position_sizing_policy`.

- [ ] **Step 1: Add failing official-sequence regression**

Create a fixture for the reconstructed 2026-06-24 through 2026-07-24 Pro1 tier states. Assert at minimum:

```text
2026-07-15: tiers 1,2,3
2026-07-16: tiers 2,3,4
2026-07-17: tiers 1,2,3,4
2026-07-23: tiers 1,2,3
2026-07-24: tiers 1,3,4
```

Also assert Pro changes do not affect an active cycle and the next empty cycle uses the new profile.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
cd backend
uv run pytest tests/test_backtest_engine.py tests/test_api_backtests.py -q
```

- [ ] **Step 3: Implement a Radar branch in the backtest engine**

Keep the current Dynamic Wave loop as its own path. Radar processing must:

1. Determine start-of-day occupied tiers.
2. Plan at most one new tier.
3. Evaluate sells independently from persisted entry rules.
4. Prevent a same-day sale from freeing a tier for that day's buy plan.
5. Reuse empty regular tiers in later trading days.
6. Use reserve tier 7 only after tiers 1-6 are occupied.
7. Apply 100% realized P/L to Capital.
8. Start a new cycle only when no position remains.

- [ ] **Step 4: Hide Dynamic Wave policies from Radar request semantics**

The API may retain optional `mode_policy` for compatibility, but Radar snapshots and execution ignore it. Store `pro_profile` in the run snapshot so results are reproducible.

- [ ] **Step 5: Run tests and commit**

Run the Task 3 focused tests plus `tests/test_dynamic_wave_strategy.py`, then commit:

```powershell
git add backend/app backend/tests frontend/src/types/api.ts
git commit -m "feat: add radar0458 pro backtest support"
```

---

### Task 4: Radar Settings, Dashboard, and Trading UI

**Files:**
- Modify: `frontend/src/components/SettingsForm.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/pages/TradesPage.tsx`
- Modify: `frontend/src/components/DailyPlanPanel.tsx`
- Modify: `frontend/src/pages/BacktestPage.tsx`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/utils/format.ts`
- Modify: `frontend/src/styles.css`
- Test: existing TypeScript build

**Interfaces:**
- Uses `strategy_type`, `radar_profile`, `radar_tier`, and `radar_cycle_capital` returned by Tasks 1-3.
- Does not show safe/aggressive or RSI controls for Radar.

- [ ] **Step 1: Add strategy-aware UI branches**

Settings:

- show Pro1/Pro2/Pro3 selector for Radar;
- force or validate SOXL;
- show fixed preset details read-only;
- hide Dynamic Wave-only fields.

Dashboard:

- replace operating-mode and Capital-cycle blocks with current Pro, cycle Capital, occupied tiers, and next tier;
- retain general portfolio and market context.

Trading:

- label buy rows with `N티어 LOC`;
- show tier and applied Pro on positions;
- preserve the existing Dynamic Wave layout when selected.

Backtest:

- show Pro selector for Radar;
- hide RSI mode policy and Dynamic Wave sizing policy.

- [ ] **Step 2: Add type-safe formatting and restrained styles**

Add `radar0458_pro: "떨사오팔 Pro"` to strategy translation. Reuse existing Professional Trading Desk components and spacing; do not add a new visual theme.

- [ ] **Step 3: Build and commit**

Run:

```powershell
cd frontend
npm run build
```

Commit:

```powershell
git add frontend/src
git commit -m "feat: add radar0458 pro operations ui"
```

---

### Task 5: Read-only Integrated Strategy Orders

**Files:**
- Create: `backend/app/dto/integrated_orders.py`
- Create: `backend/app/services/integrated_order_service.py`
- Create: `backend/app/api/routes_integrated_orders.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/app/domain/models.py`
- Modify: `backend/app/db/migrations.py`
- Create: `frontend/src/api/integratedOrders.ts`
- Create: `frontend/src/pages/IntegratedOrdersPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/styles.css`
- Test: `backend/tests/test_integrated_order_service.py`
- Test: `backend/tests/test_api_integrated_orders.py`

**Interfaces:**
- Stores inclusion separately from strategy settings in `integrated_order_preferences`.
- Produces original aggregated orders, netted orders, and source breakdown.

- [ ] **Step 1: Write failing aggregation and isolation tests**

Given included strategy source orders:

```text
dynamic_wave buy 100.00 × 3
radar pro1 tier2 buy 100.00 × 5
radar pro1 position sell 105.00 × 4
excluded strategy buy 90.00 × 10
```

Assert:

- general buy at 100.00 has quantity 8 and two sources;
- excluded order is absent;
- final rows are sorted by price descending;
- netted output equals `net_loc_orders()` for included source orders;
- changing inclusion leaves strategy config, portfolio, positions, and trades unchanged.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
cd backend
uv run pytest tests/test_integrated_order_service.py tests/test_api_integrated_orders.py -q
```

- [ ] **Step 3: Add preference storage and API**

Add migration version 5:

```sql
CREATE TABLE integrated_order_preferences (
    strategy_config_id INTEGER PRIMARY KEY,
    included BOOLEAN NOT NULL DEFAULT 0,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY(strategy_config_id) REFERENCES strategy_configs (id)
)
```

Endpoints:

```text
GET /api/integrated-orders
PUT /api/integrated-orders/preferences/{config_id}
```

The GET response includes preferences, original orders, and netted orders. Build buy sources from each included strategy's daily plan and sell sources from current sell-plan signals. Aggregate equal ticker/side/price before presenting.

- [ ] **Step 4: Build the `전략 통합 주문` page**

Add a sidebar item and page containing:

- strategy rows with `통합 주문 포함` toggles;
- `일반 주문` / `퉁치기 주문` segmented control;
- descending USD order rows;
- expandable source breakdown showing strategy name, tier, and source quantity;
- no fill, save, or position mutation controls.

- [ ] **Step 5: Run focused tests, build, and commit**

Run:

```powershell
cd backend
uv run pytest tests/test_integrated_order_service.py tests/test_api_integrated_orders.py tests/test_loc_netting.py -q
cd ../frontend
npm run build
```

Commit:

```powershell
git add backend/app backend/tests frontend/src
git commit -m "feat: add integrated strategy orders"
```

---

### Task 6: Full Regression and Isolation Verification

**Files:**
- Modify only files required by failures proven in this task.
- Test: `backend/tests/test_dynamic_wave_strategy.py`
- Test: `backend/tests/test_daily_plan_service.py`
- Test: `backend/tests/test_backtest_engine.py`
- Test: complete backend and frontend suites.

- [ ] **Step 1: Run full backend tests**

```powershell
cd backend
uv run pytest -q
```

- [ ] **Step 2: Run frontend build**

```powershell
cd frontend
npm run build
```

- [ ] **Step 3: Verify isolation invariants**

Confirm with tests and diff inspection:

- Dynamic Wave registry, plans, modes, RSI, snapshots, Capital scheduling, and backtests keep existing results.
- Radar-only nullable fields do not appear as required Dynamic Wave inputs.
- Integrated-order preferences are never read by strategy calculation services.
- Integrated order endpoints expose no mutation of trades or positions.

- [ ] **Step 4: Commit only if verification required fixes**

If fixes were needed, commit:

```powershell
git add backend/app backend/tests frontend/src
git commit -m "test: verify strategy isolation"
```

If no files changed, do not create an empty commit.
