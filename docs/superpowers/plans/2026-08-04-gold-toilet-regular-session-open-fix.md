# Gold Toilet Regular-Session Open Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unreliable current-day daily-candle open with the first SOXL regular-session one-minute bar, while preserving automatic and manual prices separately and preventing stale manual values from being resubmitted.

**Architecture:** Add a dedicated Yahoo regular-session opening-price provider that accepts only the 09:30 America/New_York one-minute bar after validating its OHLC values. Store the provider price and the optional manual override in separate columns; derive the effective price in the service response. Split percentage-sheet saving from manual-price override endpoints so an order-sheet save can never silently resend a stale manual value.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, SQLite migrations, `zoneinfo`, `httpx`, React 18, TypeScript, Vitest.

## Global Constraints

- SOXL automatic open must come only from the 09:30 America/New_York one-minute regular-session bar.
- Never fall back to a current-day `interval=1d` open.
- Do not calculate or display executable order prices until the automatic open is confirmed.
- A manual override is allowed only after the automatic open exists.
- Preserve both the automatic open and manual override; the effective open is manual when present, otherwise automatic.
- Percentage-sheet saving must never send or mutate a manual override.
- Poll every 15 seconds only for the current SOXL market date while the automatic open is waiting.
- Validate `low <= open <= high`, all three values are positive, and the bar timestamp is exactly 09:30 in America/New_York.
- Existing daily-candle captures are untrusted and must be invalidated by migration.

## Root-Cause Evidence

- The local row captured `provider_market_open=106.1500015` at 2026-08-04 13:30:16 UTC.
- Yahoo's current-day one-day candle reported open `106.15` while reporting low `129.66`, an impossible OHLC relationship.
- Yahoo's 2026-08-04 13:30 UTC one-minute bar reported open `131.505`, high `133.04`, and low `129.66`.
- The current service snapshots the first non-zero daily open and never revisits it.
- At 13:31:44 UTC, the combined order-sheet form submitted `131.5` as a manual override. This happened through the same save path as percentage inputs, so preserved browser form state can unintentionally override the automatic value.

## File Map

- Create `backend/app/infrastructure/market_data/yahoo_regular_open_provider.py`: fetch and validate the exact regular-session opening bar.
- Create `backend/tests/test_yahoo_regular_open_provider.py`: deterministic timestamp, payload, and validation tests without live network calls.
- Modify `backend/pyproject.toml` and `backend/uv.lock`: make `httpx` an explicit runtime dependency.
- Modify `backend/app/domain/models.py`: add separate manual override and provider-source fields.
- Modify `backend/app/db/migrations.py`: invalidate legacy daily captures and migrate existing manual values.
- Modify `backend/tests/test_migrations.py`: prove legacy data is transformed safely.
- Modify `backend/app/infrastructure/repositories/gold_toilet_orders.py`: separate provider capture, manual set, and manual clear operations.
- Modify `backend/app/services/gold_toilet_order_interpreter.py`: consume a regular-open interface and derive the effective price.
- Modify `backend/app/dto/gold_toilet_orders.py`: expose automatic, manual, and effective prices explicitly.
- Modify `backend/app/api/routes_gold_toilet_orders.py`: split sheet update, manual override, and manual reset endpoints.
- Modify `backend/tests/test_api_gold_toilet_orders.py`: cover waiting, automatic capture, override, reset, and owner isolation.
- Modify `frontend/src/api/goldToiletOrders.ts`: align types and add manual override/reset calls.
- Modify `frontend/src/pages/GoldToiletOrdersPage.tsx`: separate the manual override form from order-sheet saving.
- Modify `frontend/src/styles.css`: style automatic price, manual override, and warning states.
- Modify `frontend/src/utils/goldToiletOrders.test.ts`: cover polling and display-state decisions.

---

### Task 1: Exact 09:30 Regular-Session Provider

**Files:**
- Create: `backend/app/infrastructure/market_data/yahoo_regular_open_provider.py`
- Create: `backend/tests/test_yahoo_regular_open_provider.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/uv.lock`

**Interfaces:**
- Produces: `RegularSessionOpen(symbol: str, session_date: date, price: Decimal, bar_time: datetime)`.
- Produces: `YahooRegularOpenProvider.get_open(symbol: str, session_date: date) -> RegularSessionOpen | None`.
- Consumes: Yahoo chart JSON at interval `1m`; no live network is used in unit tests.

- [ ] **Step 1: Write parser tests for the exact 09:30 bar**

```python
def test_extracts_only_0930_new_york_bar() -> None:
    payload = chart_payload(
        timestamps=[1785849840, 1785849900],
        opens=[131.26, 131.505],
        highs=[131.64, 133.04],
        lows=[131.21, 129.66],
    )
    quote = parse_regular_session_open(payload, "SOXL", date(2026, 8, 4))
    assert quote is not None
    assert quote.price == Decimal("131.505")
    assert quote.bar_time.isoformat() == "2026-08-04T09:30:00-04:00"


def test_rejects_daily_style_impossible_open() -> None:
    payload = chart_payload(
        timestamps=[1785849900],
        opens=[106.15],
        highs=[133.04],
        lows=[129.66],
    )
    assert parse_regular_session_open(payload, "SOXL", date(2026, 8, 4)) is None


def test_returns_none_before_0930_bar_exists() -> None:
    payload = chart_payload(
        timestamps=[1785849840],
        opens=[131.26],
        highs=[131.64],
        lows=[131.21],
    )
    assert parse_regular_session_open(payload, "SOXL", date(2026, 8, 4)) is None
```

- [ ] **Step 2: Run the provider tests and confirm RED**

Run: `cd backend && uv run pytest tests/test_yahoo_regular_open_provider.py -q`

Expected: collection fails because `yahoo_regular_open_provider` does not exist.

- [ ] **Step 3: Add `httpx` as a runtime dependency**

Move `httpx>=0.27.0` from `[project.optional-dependencies].dev` to `[project].dependencies`, then run:

```powershell
cd backend
uv lock
uv sync --extra dev
```

- [ ] **Step 4: Implement the provider and pure parser**

```python
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx

NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class RegularSessionOpen:
    symbol: str
    session_date: date
    price: Decimal
    bar_time: datetime


class YahooRegularOpenProvider:
    def get_open(self, symbol: str, session_date: date) -> RegularSessionOpen | None:
        session_start = datetime.combine(session_date, time(9, 30), NEW_YORK)
        response = httpx.get(
            f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={
                "period1": int((session_start - timedelta(minutes=1)).timestamp()),
                "period2": int((session_start + timedelta(minutes=2)).timestamp()),
                "interval": "1m",
                "includePrePost": "false",
            },
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5.0,
        )
        response.raise_for_status()
        return parse_regular_session_open(response.json(), symbol, session_date)
```

The parser must zip timestamps with quote arrays by index, select only 09:30 New York on `session_date`, convert numeric values through `Decimal(str(value))`, and return `None` unless `low <= open <= high` and all values are positive.

- [ ] **Step 5: Run provider tests and static checks**

Run: `cd backend && uv run pytest tests/test_yahoo_regular_open_provider.py -q && uv run ruff check app tests`

Expected: all provider tests pass and Ruff reports no errors.

- [ ] **Step 6: Commit Task 1**

```powershell
git add backend/pyproject.toml backend/uv.lock backend/app/infrastructure/market_data/yahoo_regular_open_provider.py backend/tests/test_yahoo_regular_open_provider.py
git commit -m "fix: read SOXL regular session open from minute bar"
```

### Task 2: Separate Automatic and Manual Price Persistence

**Files:**
- Modify: `backend/app/domain/models.py:117-139`
- Modify: `backend/app/db/migrations.py`
- Modify: `backend/app/infrastructure/repositories/gold_toilet_orders.py:58-88`
- Modify: `backend/tests/test_migrations.py`
- Modify: `backend/tests/test_gold_toilet_order_service.py`

**Interfaces:**
- Produces: `provider_market_open`, `provider_open_observed_at`, `provider_open_source`.
- Produces: `manual_market_open`, `manual_open_observed_at`.
- Produces: repository methods `snapshot_provider_open`, `set_manual_open`, and `clear_manual_open`.
- Consumes: `RegularSessionOpen` from Task 1.

- [ ] **Step 1: Write a legacy migration test**

Create a version-11 database row with `market_open=131.5`, `open_source='manual'`, `provider_market_open=106.15`, then run migrations and assert:

```python
assert row["provider_market_open"] is None
assert row["provider_open_observed_at"] is None
assert row["provider_open_source"] is None
assert Decimal(str(row["manual_market_open"])) == Decimal("131.5")
assert row["manual_open_observed_at"] == "2026-08-04 13:31:44"
```

This invalidates every value captured by the old daily-candle method while retaining an explicit user override.

- [ ] **Step 2: Run the migration test and confirm RED**

Run: `cd backend && uv run pytest tests/test_migrations.py -q`

Expected: failure because the manual and source columns do not exist.

- [ ] **Step 3: Add migration version 12**

Add nullable columns:

```sql
ALTER TABLE gold_toilet_order_sheets ADD COLUMN provider_open_source VARCHAR(32);
ALTER TABLE gold_toilet_order_sheets ADD COLUMN manual_market_open NUMERIC(18, 6);
ALTER TABLE gold_toilet_order_sheets ADD COLUMN manual_open_observed_at DATETIME;
```

Then migrate old manual values and invalidate old provider captures:

```sql
UPDATE gold_toilet_order_sheets
SET manual_market_open = market_open,
    manual_open_observed_at = open_observed_at
WHERE open_source = 'manual';

UPDATE gold_toilet_order_sheets
SET provider_market_open = NULL,
    provider_open_observed_at = NULL,
    provider_open_source = NULL;
```

Keep legacy `market_open`, `open_source`, and `open_observed_at` columns for SQLite compatibility, but stop reading or writing them in application code.

- [ ] **Step 4: Update the SQLAlchemy model and repository**

Implement these exact repository operations:

```python
def snapshot_provider_open(
    self, sheet: GoldToiletOrderSheet, price: Decimal, observed_at: datetime
) -> GoldToiletOrderSheet:
    if sheet.provider_market_open is None:
        sheet.provider_market_open = price
        sheet.provider_open_observed_at = observed_at
        sheet.provider_open_source = "yahoo_1m_regular_session"
    return self.save(sheet)


def set_manual_open(
    self, sheet: GoldToiletOrderSheet, price: Decimal, observed_at: datetime
) -> GoldToiletOrderSheet:
    if sheet.provider_market_open is None:
        raise ValueError("자동 시가가 확인된 뒤에만 직접 입력할 수 있습니다.")
    sheet.manual_market_open = price
    sheet.manual_open_observed_at = observed_at
    return self.save(sheet)


def clear_manual_open(self, sheet: GoldToiletOrderSheet) -> GoldToiletOrderSheet:
    sheet.manual_market_open = None
    sheet.manual_open_observed_at = None
    return self.save(sheet)
```

- [ ] **Step 5: Run persistence and migration tests**

Run: `cd backend && uv run pytest tests/test_migrations.py tests/test_gold_toilet_order_service.py -q`

Expected: all tests pass, and version 12 is recorded as the latest schema version.

- [ ] **Step 6: Commit Task 2**

```powershell
git add backend/app/domain/models.py backend/app/db/migrations.py backend/app/infrastructure/repositories/gold_toilet_orders.py backend/tests/test_migrations.py backend/tests/test_gold_toilet_order_service.py
git commit -m "fix: separate automatic and manual SOXL opens"
```

### Task 3: Make the Interpreter Use the Validated Regular Open

**Files:**
- Modify: `backend/app/services/gold_toilet_order_interpreter.py:13-99`
- Modify: `backend/app/dto/gold_toilet_orders.py:18-57`
- Modify: `backend/app/api/routes_gold_toilet_orders.py`
- Modify: `backend/tests/test_api_gold_toilet_orders.py`

**Interfaces:**
- Consumes: `YahooRegularOpenProvider.get_open` from Task 1.
- Consumes: separated repository operations from Task 2.
- Produces: `effective_market_open` and `effective_open_source` in `GoldToiletOrderSheetDto`.
- Produces: `PUT /api/gold-toilet/order-sheet/{order_date}/manual-open`.
- Produces: `DELETE /api/gold-toilet/order-sheet/{order_date}/manual-open`.

- [ ] **Step 1: Replace the fake daily provider in API tests**

```python
class FakeRegularOpenProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.quote: RegularSessionOpen | None = None

    def get_open(self, symbol: str, session_date: date) -> RegularSessionOpen | None:
        self.calls += 1
        return self.quote
```

Add tests proving:

```python
def test_sheet_save_cannot_submit_manual_open(...):
    response = client.put("/api/gold-toilet/order-sheet/2026-08-04", json={
        "entry_percent": "1.49",
        "allocation_percent": "22.5",
        "loc_percent": "-9.34",
        "market_open": "131.5",
    })
    assert response.status_code == 422


def test_manual_override_preserves_provider_open(...):
    # Provider captures 131.505 first.
    response = client.put(
        "/api/gold-toilet/order-sheet/2026-08-04/manual-open",
        json={"market_open": "131.50"},
    )
    sheet = response.json()["sheet"]
    assert sheet["provider_market_open"] == "131.505000"
    assert sheet["manual_market_open"] == "131.500000"
    assert sheet["effective_market_open"] == "131.500000"
    assert sheet["effective_open_source"] == "manual"


def test_manual_reset_restores_provider_open(...):
    response = client.delete(
        "/api/gold-toilet/order-sheet/2026-08-04/manual-open"
    )
    sheet = response.json()["sheet"]
    assert sheet["manual_market_open"] is None
    assert sheet["effective_market_open"] == "131.505000"
```

- [ ] **Step 2: Run API tests and confirm RED**

Run: `cd backend && uv run pytest tests/test_api_gold_toilet_orders.py -q`

Expected: failures for the missing provider interface, fields, and endpoints.

- [ ] **Step 3: Derive the effective open in one service method**

```python
def _effective_open(sheet: GoldToiletOrderSheet) -> tuple[Decimal | None, str | None]:
    if sheet.provider_market_open is None:
        return None, None
    if sheet.manual_market_open is not None:
        return sheet.manual_market_open, "manual"
    return sheet.provider_market_open, "yahoo_1m_regular_session"
```

Use this value for both the response and `calculate_gold_toilet_order`. The automatic capture path must call `get_open("SOXL", sheet.order_date)` and persist only when a validated quote is returned.

- [ ] **Step 4: Split the API contracts**

Remove `market_open` from `GoldToiletOrderSheetUpdateDto`. Add:

```python
class GoldToiletManualOpenUpdateDto(BaseModel):
    market_open: Decimal = Field(gt=0)
```

Implement the two manual endpoints. Return HTTP 409 when automatic open is still missing and HTTP 404 when the owner's sheet does not exist.

- [ ] **Step 5: Run API tests and the backend suite**

Run: `cd backend && uv run pytest tests/test_api_gold_toilet_orders.py -q && uv run pytest -q && uv run ruff check app tests`

Expected: all API tests, the full backend suite, and Ruff pass.

- [ ] **Step 6: Commit Task 3**

```powershell
git add backend/app/services/gold_toilet_order_interpreter.py backend/app/dto/gold_toilet_orders.py backend/app/api/routes_gold_toilet_orders.py backend/tests/test_api_gold_toilet_orders.py
git commit -m "fix: gate manual SOXL open behind validated automatic open"
```

### Task 4: Split the Manual Override UI from Order-Sheet Saving

**Files:**
- Modify: `frontend/src/api/goldToiletOrders.ts`
- Modify: `frontend/src/pages/GoldToiletOrdersPage.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/utils/goldToiletOrders.ts`
- Modify: `frontend/src/utils/goldToiletOrders.test.ts`

**Interfaces:**
- Consumes: automatic/manual/effective DTO fields and manual endpoints from Task 3.
- Produces: a percentage-only order-sheet form.
- Produces: a separate explicit manual override form and reset action.

- [ ] **Step 1: Add failing UI-state utility tests**

```typescript
it("allows manual override only after automatic open", () => {
  expect(canOverrideOpen(null)).toBe(false);
  expect(canOverrideOpen("131.505000")).toBe(true);
});

it("uses manual open only when the API marks it effective", () => {
  expect(openDisplay("131.505000", null)).toEqual({ price: "131.505000", source: "automatic" });
  expect(openDisplay("131.505000", "131.500000")).toEqual({ price: "131.500000", source: "manual" });
});
```

- [ ] **Step 2: Run the utility tests and confirm RED**

Run: `cd frontend && npm.cmd test -- --run src/utils/goldToiletOrders.test.ts`

Expected: failures because `canOverrideOpen` and `openDisplay` do not exist.

- [ ] **Step 3: Update frontend API types and methods**

Define `provider_market_open`, `manual_market_open`, `effective_market_open`, and `effective_open_source`. Remove `market_open` from `updateGoldToiletOrderSheet`, and add:

```typescript
export function setGoldToiletManualOpen(orderDate: string, marketOpen: string) {
  return apiPut<GoldToiletOrderResponse>(
    `/api/gold-toilet/order-sheet/${encodeURIComponent(orderDate)}/manual-open`,
    { market_open: marketOpen },
  );
}

export function clearGoldToiletManualOpen(orderDate: string) {
  return apiDelete(
    `/api/gold-toilet/order-sheet/${encodeURIComponent(orderDate)}/manual-open`,
  );
}
```

- [ ] **Step 4: Separate the two forms**

The `주문표 저장 · 해석` handler must send only the three percentages. Place manual input in a separate panel shown after `provider_market_open` exists, with the explicit button label `직접 입력값 강제 적용`. After success, clear the input state and reload.

When a manual override exists, display:

- `적용 시가 $131.50 · 직접 입력`
- `자동 시가 $131.51 · 09:30 정규장 1분봉`
- Button: `자동 시가로 되돌리기`

When the automatic open is missing, disable the manual form and display `09:30 정규장 첫 1분봉을 기다리는 중입니다.`

- [ ] **Step 5: Run frontend tests and production build**

Run: `cd frontend && npm.cmd test -- --run && npm.cmd run build`

Expected: all Vitest tests pass and Vite builds without TypeScript errors.

- [ ] **Step 6: Commit Task 4**

```powershell
git add frontend/src/api/goldToiletOrders.ts frontend/src/pages/GoldToiletOrdersPage.tsx frontend/src/styles.css frontend/src/utils/goldToiletOrders.ts frontend/src/utils/goldToiletOrders.test.ts
git commit -m "fix: make SOXL manual open override explicit"
```

### Task 5: End-to-End Verification and Operational Evidence

**Files:**
- Modify: `docs/superpowers/specs/2026-08-04-gold-toilet-order-interpreter-design.md`
- Modify: `docs/superpowers/plans/2026-08-04-gold-toilet-order-interpreter.md`

**Interfaces:**
- Consumes: the completed backend and frontend behavior from Tasks 1-4.
- Produces: documented source semantics and reproducible verification evidence.

- [ ] **Step 1: Add a deterministic regression fixture for the observed bad payload**

Save the minimal JSON values directly in `test_yahoo_regular_open_provider.py`: daily-style open `106.15`, minute open `131.505`, high `133.04`, and low `129.66`. Do not call Yahoo from the test suite.

- [ ] **Step 2: Verify the full tree**

Run:

```powershell
cd backend
uv run pytest -q
uv run ruff check app tests
cd ../frontend
npm.cmd test -- --run
npm.cmd run build
cd ..
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 3: Verify against a live Yahoo minute response without mutating the database**

Run a read-only provider command for the current SOXL market date and print the selected bar time, open, high, and low. Confirm the selected timestamp is exactly 09:30 America/New_York and `low <= open <= high`.

- [ ] **Step 4: Restart localhost and verify the user flow**

Verify these states in order:

1. Before 09:30 bar availability: `조회 대기`, no calculation, manual override disabled.
2. After the 09:30 bar appears: automatic price shown and calculation enabled.
3. Saving percentages does not change either stored price.
4. Explicit manual override changes only the effective price.
5. Reset restores the automatic price.

- [ ] **Step 5: Update the design documents**

Document that FinanceDataReader daily candles remain suitable for completed daily history but are forbidden for same-day opening-price execution. Record `yahoo_1m_regular_session` as the automatic-open source and explain the automatic/manual/effective field separation.

- [ ] **Step 6: Commit Task 5**

```powershell
git add docs/superpowers/specs/2026-08-04-gold-toilet-order-interpreter-design.md docs/superpowers/plans/2026-08-04-gold-toilet-order-interpreter.md backend/tests/test_yahoo_regular_open_provider.py
git commit -m "docs: record regular-session open safeguards"
```

## Self-Review Results

- Spec coverage: the plan covers the wrong daily candle, exact 09:30 selection, OHLC validation, polling, automatic/manual separation, legacy-data invalidation, accidental resubmission prevention, reset behavior, and full regression verification.
- Placeholder scan: no deferred implementation steps or unspecified error handling remain.
- Type consistency: `RegularSessionOpen`, provider/manual/effective DTO fields, repository methods, and endpoint names are consistent across tasks.
