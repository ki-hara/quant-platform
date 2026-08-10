# Yahoo Daily Open Capture Implementation Plan

> **For Codex:** Execute this plan test-first and verify every layer before claiming completion.

**Goal:** Capture SOXL's Yahoo daily-candle open as soon as it appears after the DST-aware regular-session start, independently of browser activity.

**Architecture:** A strict daily-candle provider validates the requested New York session date. A FastAPI lifespan collector checks unresolved current-date order sheets, begins provider calls five seconds before the calculated New York open, retries once per second, and persists the first valid open once. The UI polls the backend once per second only while the current sheet remains unresolved.

**Tech Stack:** Python 3.12, FastAPI lifespan tasks, asyncio, SQLAlchemy, httpx, React, TypeScript, Vitest, pytest.

---

### Task 1: Replace one-minute parsing with current-day daily-candle parsing

**Files:**
- Modify: `backend/tests/test_yahoo_regular_open_provider.py`
- Modify: `backend/app/infrastructure/market_data/yahoo_regular_open_provider.py`

1. Add failing tests for exact target-date selection, prior-day rejection, pre-open rejection, missing forming OHLC fields, and invalid open values.
2. Run the provider test module and confirm the new assertions fail against the one-minute parser.
3. Change the Yahoo request to `interval=1d`, use a target-date window, validate time with `America/New_York`, and accept only a positive finite open after regular-session start.
4. Run the provider tests until green.

### Task 2: Add a DST-aware server collector

**Files:**
- Create: `backend/tests/test_gold_toilet_open_collector.py`
- Create: `backend/app/services/gold_toilet_open_collector.py`
- Modify: `backend/app/infrastructure/repositories/gold_toilet_orders.py`
- Modify: `backend/app/infrastructure/repositories/gold_toilet_orders.py`
- Modify: `backend/app/main.py`

1. Add failing tests asserting the collection window begins at 13:29:55 UTC on an EDT date and 14:29:55 UTC on an EST date.
2. Add failing tests proving an unresolved current-date sheet is captured without an API request, provider failures retry, and a saved open is never overwritten.
3. Implement pure session timing helpers with `ZoneInfo("America/New_York")`.
4. Add repository lookup for unresolved sheets by order date.
5. Implement a one-second async loop that calls blocking provider/database work in a thread only during the active capture window.
6. Start and cancel the collector in the FastAPI lifespan, preserving clean shutdown.
7. Run collector and API tests until green.

### Task 3: Update source identity and UI refresh behavior

**Files:**
- Modify: `backend/app/infrastructure/repositories/gold_toilet_orders.py`
- Modify: `backend/app/services/gold_toilet_order_interpreter.py`
- Modify: `backend/tests/test_api_gold_toilet_orders.py`
- Modify: `frontend/src/utils/goldToiletOrders.ts`
- Modify: `frontend/src/utils/goldToiletOrders.test.ts`
- Modify: `frontend/src/pages/GoldToiletOrdersPage.tsx`

1. Change backend expectations to `yahoo_1d_regular_session` and run the API tests to observe failure.
2. Persist and return the new source name.
3. Change the frontend polling test from five seconds to one second and confirm failure.
4. Set the waiting poll interval to one second and update user-facing source/status text from first-minute candle to Yahoo daily open.
5. Run frontend unit tests and build.

### Task 4: Full verification

1. Run all backend tests.
2. Run backend Ruff checks.
3. Run all frontend tests.
4. Run the production frontend build.
5. Review `git diff` and `git status` to ensure only intended files changed.
