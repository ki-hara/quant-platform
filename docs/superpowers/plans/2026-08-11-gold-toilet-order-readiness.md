# Gold Toilet Order Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the allocation amount before the market open, expose separate quantities for the regular and LOC orders, and allow a manual open after the New York regular session starts even when Yahoo has not supplied an open.

**Architecture:** The backend remains the source of truth for monetary calculations and session timing. It returns a top-level allocation amount and a DST-aware manual-entry permission independently of the effective open, while the full order calculation continues to use either the manual open or the Yahoo open. The frontend renders the early allocation card and maps the completed calculation into four broker-ready order cards.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Pydantic, pytest, React 18, TypeScript, Vitest, CSS.

## Global Constraints

- Use `America/New_York` and 09:30 local time to gate manual entry.
- Keep Yahoo background collection running regardless of manual input.
- Prefer the manual open for calculations whenever it exists.
- Keep both order quantities identical and based on the lower of the two order prices.
- Perform all money calculations in the backend with `Decimal` and cent rounding.
- Do not add dependencies.

---

### Task 1: Return Allocation Amount Before the Open

**Files:**
- Modify: `backend/app/services/gold_toilet_order_service.py`
- Modify: `backend/app/dto/gold_toilet_orders.py`
- Modify: `backend/app/services/gold_toilet_order_interpreter.py`
- Test: `backend/tests/test_gold_toilet_order_service.py`
- Test: `backend/tests/test_api_gold_toilet_orders.py`

**Interfaces:**
- Produces: `calculate_allocation_amount(capital: Decimal, allocation_percent: Decimal) -> Decimal`
- Produces: `GoldToiletOrderResponseDto.allocation_amount: Decimal | None`
- Consumes: saved account capital and saved order-sheet allocation percentage.

- [ ] **Step 1: Add a failing service test for the independent allocation calculation**

```python
def test_calculates_allocation_amount_without_market_open() -> None:
    assert calculate_allocation_amount(
        Decimal("10000"), Decimal("22.5")
    ) == Decimal("2250.00")
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `uv run pytest tests/test_gold_toilet_order_service.py::test_calculates_allocation_amount_without_market_open -q`

Expected: FAIL because `calculate_allocation_amount` does not exist.

- [ ] **Step 3: Add a failing API assertion for allocation without an open**

Update the provider-failure API test so that, after saving account and sheet, it asserts:

```python
payload = response.json()
assert payload["allocation_amount"] == "2250.00"
assert payload["calculation"] is None
```

- [ ] **Step 4: Run the API test and verify RED**

Run: `uv run pytest tests/test_api_gold_toilet_orders.py -q`

Expected: FAIL because the response does not contain top-level `allocation_amount`.

- [ ] **Step 5: Implement the independent calculation and response field**

Add to `gold_toilet_order_service.py`:

```python
def calculate_allocation_amount(
    capital: Decimal, allocation_percent: Decimal
) -> Decimal:
    return _money(capital * allocation_percent / HUNDRED)
```

Use this function inside `calculate_gold_toilet_order`. Add `allocation_amount: Decimal | None` to `GoldToiletOrderResponseDto`, and populate it in `_response` whenever both account and sheet exist, before checking for an effective open.

- [ ] **Step 6: Run focused backend tests and verify GREEN**

Run: `uv run pytest tests/test_gold_toilet_order_service.py tests/test_api_gold_toilet_orders.py -q`

Expected: PASS.

- [ ] **Step 7: Commit the allocation response**

```bash
git add backend/app/services/gold_toilet_order_service.py backend/app/dto/gold_toilet_orders.py backend/app/services/gold_toilet_order_interpreter.py backend/tests/test_gold_toilet_order_service.py backend/tests/test_api_gold_toilet_orders.py
git commit -m "feat: expose gold toilet allocation before open"
```

---

### Task 2: Allow Manual Open After the Regular Session Starts

**Files:**
- Modify: `backend/app/dto/gold_toilet_orders.py`
- Modify: `backend/app/infrastructure/repositories/gold_toilet_orders.py`
- Modify: `backend/app/services/gold_toilet_order_interpreter.py`
- Test: `backend/tests/test_api_gold_toilet_orders.py`

**Interfaces:**
- Produces: `manual_open_allowed(order_date: date, now: datetime) -> bool`
- Produces: `GoldToiletOrderResponseDto.manual_open_allowed: bool`
- Changes: `GoldToiletOrderInterpreter.set_manual_open` rejects only when the New York 09:30 gate has not opened.
- Changes: `_effective_open` returns manual first, then Yahoo.

- [ ] **Step 1: Add failing DST-aware permission tests**

```python
def test_manual_open_permission_starts_at_new_york_open_in_edt_and_est() -> None:
    assert manual_open_allowed(
        date(2026, 8, 4), datetime(2026, 8, 4, 13, 29, 59, tzinfo=UTC)
    ) is False
    assert manual_open_allowed(
        date(2026, 8, 4), datetime(2026, 8, 4, 13, 30, tzinfo=UTC)
    ) is True
    assert manual_open_allowed(
        date(2026, 11, 3), datetime(2026, 11, 3, 14, 30, tzinfo=UTC)
    ) is True
```

- [ ] **Step 2: Run the permission test and verify RED**

Run: `uv run pytest tests/test_api_gold_toilet_orders.py::test_manual_open_permission_starts_at_new_york_open_in_edt_and_est -q`

Expected: FAIL because `manual_open_allowed` does not exist.

- [ ] **Step 3: Replace the old rejection test with a failing recovery test**

With the fake Yahoo provider returning `opening_bar_not_available`, save account and sheet, submit a manual open, and assert:

```python
assert response.status_code == 200
payload = response.json()
assert payload["sheet"]["provider_market_open"] is None
assert payload["sheet"]["manual_market_open"] == "131.500000"
assert payload["sheet"]["effective_market_open"] == "131.500000"
assert payload["sheet"]["effective_open_source"] == "manual"
assert payload["calculation"] is not None
assert payload["open_status"] == "ready"
```

- [ ] **Step 4: Run the recovery test and verify RED**

Run: `uv run pytest tests/test_api_gold_toilet_orders.py -q`

Expected: FAIL with HTTP 409 from the repository guard.

- [ ] **Step 5: Implement the DST-aware gate and manual-first effective open**

Add:

```python
def manual_open_allowed(order_date: date, now: datetime) -> bool:
    aware_now = now.replace(tzinfo=UTC) if now.tzinfo is None else now
    session_start = datetime.combine(order_date, time(9, 30), NEW_YORK)
    return aware_now.astimezone(NEW_YORK) >= session_start
```

Remove the provider-open guard from `GoldToiletOrderRepository.set_manual_open`. In `GoldToiletOrderInterpreter.set_manual_open`, raise `ValueError` before saving when the helper returns false. Change `_effective_open` to test `manual_market_open` before `provider_market_open`. Compute `open_status` from `effective_open is not None`. Return `manual_open_allowed` in every response.

- [ ] **Step 6: Add and pass the reset-without-provider test**

After applying a manual open while Yahoo remains unavailable, delete it and assert:

```python
assert payload["sheet"]["manual_market_open"] is None
assert payload["sheet"]["effective_market_open"] is None
assert payload["calculation"] is None
assert payload["open_status"] in {"waiting", "failed"}
```

Run: `uv run pytest tests/test_api_gold_toilet_orders.py -q`

Expected: PASS.

- [ ] **Step 7: Run collector regression tests**

Run: `uv run pytest tests/test_gold_toilet_open_collector.py tests/test_yahoo_regular_open_provider.py -q`

Expected: PASS, proving automatic collection remains independent of manual input.

- [ ] **Step 8: Commit the manual recovery flow**

```bash
git add backend/app/dto/gold_toilet_orders.py backend/app/infrastructure/repositories/gold_toilet_orders.py backend/app/services/gold_toilet_order_interpreter.py backend/tests/test_api_gold_toilet_orders.py
git commit -m "feat: allow manual open recovery after market start"
```

---

### Task 3: Render Early Allocation and Four Order Cards

**Files:**
- Modify: `frontend/src/api/goldToiletOrders.ts`
- Modify: `frontend/src/utils/goldToiletOrders.ts`
- Modify: `frontend/src/utils/goldToiletOrders.test.ts`
- Modify: `frontend/src/pages/GoldToiletOrdersPage.tsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: `GoldToiletOrderResponse.allocation_amount: string | null`
- Consumes: `GoldToiletOrderResponse.manual_open_allowed: boolean`
- Produces: `goldToiletOrderResultItems(calculation: GoldToiletCalculation | null)` returning four display items.

- [ ] **Step 1: Add failing frontend helper tests**

```typescript
it("builds separate regular and LOC quantity cards", () => {
  const items = goldToiletOrderResultItems({
    breakout_buy_price: "48.97",
    order_quantity: 51,
    loc_buy_price: "43.74",
    allocation_amount: "2250.00",
    required_reservation_cash: "4728.21",
    cash_warning: false,
  });

  expect(items.map((item) => item.label)).toEqual([
    "매수가",
    "매수가 주문 수량",
    "LOC 매수가",
    "LOC 주문 수량",
  ]);
  expect(items[1].copyValue).toBe(51);
  expect(items[3].copyValue).toBe(51);
});
```

- [ ] **Step 2: Run the frontend test and verify RED**

Run: `npm.cmd test -- --run src/utils/goldToiletOrders.test.ts`

Expected: FAIL because `goldToiletOrderResultItems` does not exist.

- [ ] **Step 3: Add response types and implement the result-item helper**

Add `allocation_amount: string | null` and `manual_open_allowed: boolean` to `GoldToiletOrderResponse`. Implement the helper with exactly four items, formatted values, copy values, and `price` or `quantity` kinds.

- [ ] **Step 4: Update the page layout**

- Render a dedicated allocation card above `OpenStatus` using top-level `data.allocation_amount`.
- Render the four result items from the helper instead of the current three hard-coded cards.
- Use `data.manual_open_allowed` instead of `canOverrideOpen(providerOpen)` to enable manual input.
- Keep `자동 시가로 되돌리기` visible whenever `manual_market_open` exists.
- Update the explanatory copy so it states that direct entry opens at the New York regular-session start and automatic lookup continues.

- [ ] **Step 5: Update responsive styling**

Set `.gold-order-results` to four equal columns on wide screens and retain the existing one-column mobile layout. Add a focused allocation-card style that visually precedes the market-open status without competing with the large market-open card.

- [ ] **Step 6: Run focused frontend tests and verify GREEN**

Run: `npm.cmd test -- --run src/utils/goldToiletOrders.test.ts`

Expected: PASS.

- [ ] **Step 7: Run the frontend suite and build**

Run: `npm.cmd test -- --run`

Expected: all tests PASS.

Run: `npm.cmd run build`

Expected: TypeScript and Vite production build PASS.

- [ ] **Step 8: Commit the UI changes**

```bash
git add frontend/src/api/goldToiletOrders.ts frontend/src/utils/goldToiletOrders.ts frontend/src/utils/goldToiletOrders.test.ts frontend/src/pages/GoldToiletOrdersPage.tsx frontend/src/styles.css
git commit -m "feat: show gold toilet order readiness details"
```

---

### Task 4: Full Verification and Main Deployment Readiness

**Files:**
- Verify all files changed by Tasks 1-3.

**Interfaces:**
- Consumes: completed backend and frontend behavior.
- Produces: a clean, tested commit series ready for `origin/main`.

- [ ] **Step 1: Run backend lint and the full backend suite**

Run: `uv run ruff check app tests`

Expected: PASS.

Run: `uv run pytest -q`

Expected: all tests PASS.

- [ ] **Step 2: Run the full frontend suite and production build**

Run: `npm.cmd test -- --run`

Expected: all tests PASS.

Run: `npm.cmd run build`

Expected: PASS.

- [ ] **Step 3: Inspect the final diff**

Run: `git diff origin/main --check`

Expected: no whitespace errors.

Run: `git status --short`

Expected: only the intended feature commits are ahead of `origin/main` and the worktree is clean.

- [ ] **Step 4: Review runtime invariants**

Confirm from code and tests:

- allocation amount exists before an open;
- manual entry is forbidden before New York 09:30 and allowed afterward;
- manual input works without Yahoo data;
- Yahoo background collection still processes unresolved provider opens;
- clearing manual input falls back to Yahoo or waiting;
- both visible order quantities are identical.
