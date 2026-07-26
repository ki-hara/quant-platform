# Start-of-Day Split Limit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent a backtest that starts a trading day at its configured split limit from using a same-day sale to authorize a replacement buy.

**Architecture:** Add a small predicate to `BacktestEngine` that resolves the current mode's configured `split_count` and compares it with the position count captured before any daily sells. Preserve the existing sell-first execution path, but invoke the existing buy path only when the start-of-day predicate permits it.

**Tech Stack:** Python 3.12, `Decimal`, pytest, existing strategy and backtest-engine abstractions

## Global Constraints

- A trading day that starts with `starting_open_position_count >= split_count` must not evaluate or execute a buy that day.
- Sells continue to execute normally on a blocked day.
- A tier freed by a sell becomes buy-eligible on the next trading day.
- A day that starts below the split limit retains the existing sell-first, then buy behavior.
- Resolve `split_count` from the current date's effective mode; do not hard-code seven.
- If a strategy's settings have no usable positive `split_count`, preserve the current behavior and do not add an engine-level block.
- Do not change database schemas, API contracts, frontend code, live-trading execution, or LOC netting.
- Preserve the unrelated existing modification in `docs/superpowers/plans/2026-06-26-strategy-operations-ui-implementation.md`.

---

### Task 1: Add the start-of-day split-limit predicate

**Files:**
- Modify: `backend/app/backtest_engine/engine.py:280`
- Test: `backend/tests/test_backtest_engine.py`

**Interfaces:**
- Consumes: `settings: dict`, `effective_mode: StrategyMode`, and `starting_open_position_count: int`
- Produces: `BacktestEngine._is_start_of_day_split_limit_reached(settings, effective_mode, starting_open_position_count) -> bool`

- [ ] **Step 1: Write failing predicate tests**

Append these tests before the helper functions at the bottom of `backend/tests/test_backtest_engine.py`:

```python
def test_start_of_day_split_limit_uses_effective_mode_configuration() -> None:
    settings = {
        "safe": {"split_count": 7},
        "aggressive": {"split_count": 5},
    }
    engine = BacktestEngine()

    assert engine._is_start_of_day_split_limit_reached(
        settings,
        StrategyMode.SAFE,
        starting_open_position_count=6,
    ) is False
    assert engine._is_start_of_day_split_limit_reached(
        settings,
        StrategyMode.SAFE,
        starting_open_position_count=7,
    ) is True
    assert engine._is_start_of_day_split_limit_reached(
        settings,
        StrategyMode.AGGRESSIVE,
        starting_open_position_count=5,
    ) is True


def test_start_of_day_split_limit_is_disabled_without_a_positive_limit() -> None:
    engine = BacktestEngine()

    assert engine._is_start_of_day_split_limit_reached(
        {},
        StrategyMode.SAFE,
        starting_open_position_count=7,
    ) is False
    assert engine._is_start_of_day_split_limit_reached(
        {"safe": {"split_count": 0}},
        StrategyMode.SAFE,
        starting_open_position_count=7,
    ) is False
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest tests/test_backtest_engine.py -k "start_of_day_split_limit" -v
```

Expected: both tests fail with `AttributeError: 'BacktestEngine' object has no attribute '_is_start_of_day_split_limit_reached'`.

- [ ] **Step 3: Implement the predicate**

Add this method immediately before `_sell_positions` in `backend/app/backtest_engine/engine.py`:

```python
    def _is_start_of_day_split_limit_reached(
        self,
        settings: dict,
        effective_mode: StrategyMode,
        starting_open_position_count: int,
    ) -> bool:
        mode_settings = settings.get(effective_mode.value)
        if not isinstance(mode_settings, dict):
            return False
        split_count = int(mode_settings.get("split_count", 0))
        return split_count > 0 and starting_open_position_count >= split_count
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest tests/test_backtest_engine.py -k "start_of_day_split_limit" -v
```

Expected: `2 passed`.

- [ ] **Step 5: Commit the predicate and its tests**

```powershell
git add backend/app/backtest_engine/engine.py backend/tests/test_backtest_engine.py
git commit -m "test: define start-of-day split limit"
```

---

### Task 2: Gate daily buys using the pre-sell position count

**Files:**
- Modify: `backend/app/backtest_engine/engine.py:74-156`
- Test: `backend/tests/test_backtest_engine.py`

**Interfaces:**
- Consumes: `BacktestEngine._is_start_of_day_split_limit_reached(...) -> bool` from Task 1
- Produces: daily execution ordering in which sells occur normally, while a fully occupied start-of-day ladder cannot buy until a later trading day

- [ ] **Step 1: Add a deterministic test strategy**

Extend the imports in `backend/tests/test_backtest_engine.py`:

```python
from app.strategy_engine.base import BuySignal, CapitalUpdate, PositionSize, SellSignal, Strategy
from app.strategy_engine.context import StrategyContext, StrategyPosition
```

Add this strategy below `assert_money`:

```python
class _ScheduledReplacementStrategy(Strategy):
    strategy_type = "scheduled_replacement"
    display_name = "Scheduled Replacement Strategy"

    def __init__(self, sell_date: date, sell_buy_date: date) -> None:
        self.sell_date = sell_date
        self.sell_buy_date = sell_buy_date

    def get_mode(self, context: StrategyContext) -> StrategyMode:
        return context.effective_mode

    def should_buy(self, context: StrategyContext) -> BuySignal:
        return BuySignal(context.current_date <= self.sell_buy_date, "scheduled_buy")

    def should_sell(self, context: StrategyContext, position: StrategyPosition) -> SellSignal:
        should_sell = (
            context.current_date == self.sell_date
            and position.buy_date == date(2026, 1, 2)
        )
        return SellSignal(should_sell, "scheduled_sell" if should_sell else None)

    def calculate_position_size(self, context: StrategyContext) -> PositionSize:
        return PositionSize(amount=Decimal("1"), quantity=1)

    def update_capital(self, context: StrategyContext, realized_pnl: Decimal) -> CapitalUpdate:
        return CapitalUpdate(context.capital)

    def get_settings_schema(self) -> dict:
        return {"type": "object", "fields": {}}
```

The constructor's `sell_buy_date` keeps buying enabled through the assertion window without coupling the test to price thresholds.

- [ ] **Step 2: Write the failing seven-position regression test**

Add:

```python
def test_full_ladder_sell_does_not_fund_same_day_replacement_buy() -> None:
    prices = [
        _price(date(2026, 1, day), "10")
        for day in range(1, 11)
    ]
    result = BacktestEngine().run(
        strategy=_ScheduledReplacementStrategy(
            sell_date=date(2026, 1, 9),
            sell_buy_date=date(2026, 1, 10),
        ),
        prices=prices,
        initial_capital=Decimal("100"),
        fee_rate=Decimal("0"),
        slippage_rate=Decimal("0"),
        settings={
            "safe": {"split_count": 7},
            "capital_update": {"type": "trading_days", "interval": 0},
        },
    )

    trades_on_sell_date = [
        trade for trade in result.trades if trade.date == date(2026, 1, 9)
    ]
    trades_on_next_date = [
        trade for trade in result.trades if trade.date == date(2026, 1, 10)
    ]

    assert [trade.side for trade in trades_on_sell_date] == ["SELL"]
    assert trades_on_sell_date[0].open_position_count == 6
    assert [trade.side for trade in trades_on_next_date] == ["BUY"]
    assert trades_on_next_date[0].open_position_count == 7
```

- [ ] **Step 3: Write the below-limit compatibility test**

Add:

```python
def test_below_limit_start_preserves_same_day_sell_then_buy_behavior() -> None:
    prices = [
        _price(date(2026, 1, day), "10")
        for day in range(1, 9)
    ]
    result = BacktestEngine().run(
        strategy=_ScheduledReplacementStrategy(
            sell_date=date(2026, 1, 8),
            sell_buy_date=date(2026, 1, 8),
        ),
        prices=prices,
        initial_capital=Decimal("100"),
        fee_rate=Decimal("0"),
        slippage_rate=Decimal("0"),
        settings={
            "safe": {"split_count": 7},
            "capital_update": {"type": "trading_days", "interval": 0},
        },
    )

    trades_on_sell_date = [
        trade for trade in result.trades if trade.date == date(2026, 1, 8)
    ]

    assert [trade.side for trade in trades_on_sell_date] == ["SELL", "BUY"]
    assert [trade.open_position_count for trade in trades_on_sell_date] == [5, 6]
```

- [ ] **Step 4: Run the regression tests and verify the full-ladder case fails**

Run:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest tests/test_backtest_engine.py -k "full_ladder_sell or below_limit_start" -v
```

Expected before wiring the predicate:

- `test_full_ladder_sell_does_not_fund_same_day_replacement_buy` fails because the trades on 2026-01-09 are `["SELL", "BUY"]`.
- `test_below_limit_start_preserves_same_day_sell_then_buy_behavior` passes, preserving the existing behavior.

- [ ] **Step 5: Capture start-of-day state and guard only the buy path**

In `BacktestEngine.run`, capture the count before `_sell_positions` and compute the block from the current day's effective mode:

```python
            if index > 0:
                starting_open_position_count = len(open_positions)
                buy_blocked_at_start = self._is_start_of_day_split_limit_reached(
                    settings,
                    effective_mode,
                    starting_open_position_count,
                )
                cash, cumulative_fees, realized_today, sell_trades = self._sell_positions(
```

Keep sell processing unchanged. Wrap the context rebuild and existing buy execution block, from the current `context = self._build_context(...)` immediately after sell processing through `next_position_id += 1`, in:

```python
                if not buy_blocked_at_start:
                    context = self._build_context(
                        price=price,
                        previous_close=previous_close,
                        capital=capital,
                        cash=cash,
                        open_positions=open_positions,
                        settings=settings,
                        trading_day_index=index,
                        effective_mode=effective_mode,
                    )
                    buy_signal = strategy.should_buy(context)
                    if buy_signal.should_buy:
                        # Preserve the existing position sizing, cash check,
                        # trade creation, and next_position_id increment here.
```

Do not move capital-update scheduling or snapshot creation into this conditional. A blocked buy day must still update realized capital on schedule and emit a daily snapshot.

- [ ] **Step 6: Run the regression tests and verify both pass**

Run:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest tests/test_backtest_engine.py -k "full_ladder_sell or below_limit_start" -v
```

Expected: `2 passed`.

- [ ] **Step 7: Run all backtest-engine tests**

Run:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest tests/test_backtest_engine.py -v
```

Expected: all tests in `test_backtest_engine.py` pass. Existing expected trade sequences remain unchanged except the new regression scenario.

- [ ] **Step 8: Commit the daily execution change**

```powershell
git add backend/app/backtest_engine/engine.py backend/tests/test_backtest_engine.py
git commit -m "fix: delay full-ladder replacement buys"
```

---

### Task 3: Verify backend-wide behavior

**Files:**
- Verify: `backend/app/backtest_engine/engine.py`
- Verify: `backend/tests/test_backtest_engine.py`
- Preserve: `docs/superpowers/plans/2026-06-26-strategy-operations-ui-implementation.md`

**Interfaces:**
- Consumes: completed Tasks 1 and 2
- Produces: verification evidence that the timing change does not regress strategy, service, API, cash, fee, capital-update, or metric behavior

- [ ] **Step 1: Run formatting and lint checks on changed Python files**

Run:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m ruff check app/backtest_engine/engine.py tests/test_backtest_engine.py
.\.venv\Scripts\python.exe -m ruff format --check app/backtest_engine/engine.py tests/test_backtest_engine.py
```

Expected: both commands exit with code `0`.

- [ ] **Step 2: Run the complete backend test suite**

Run:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: the complete suite passes with zero failures.

- [ ] **Step 3: Inspect the final diff and working tree**

Run from the repository root:

```powershell
git diff --check HEAD~2..HEAD
git diff --stat HEAD~2..HEAD
git status --short
```

Expected:

- `git diff --check` reports no whitespace errors.
- The two implementation commits modify only `backend/app/backtest_engine/engine.py` and `backend/tests/test_backtest_engine.py`.
- `git status --short` still lists only the pre-existing unrelated modification to `docs/superpowers/plans/2026-06-26-strategy-operations-ui-implementation.md`.

- [ ] **Step 4: Record the verification result**

Do not create a third commit when no files changed. Report the focused test count, complete backend test count, lint result, and the preserved unrelated working-tree modification in the implementation handoff.

