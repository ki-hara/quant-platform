# Gold Toilet Order Interpreter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an authenticated Gold Toilet page that saves the daily order sheet and produces a breakout price, LOC-based shared quantity, and LOC price from the SOXL opening price.

**Architecture:** Add owner-scoped SQLAlchemy models and a focused calculation/open-price service behind authenticated FastAPI routes. The React page only edits inputs, polls until the backend snapshots today's open, and renders the three server-calculated outputs.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, SQLite migrations, Decimal, React 18, TypeScript, Vitest.

## Global Constraints

- Both orders use one shared quantity calculated from the LOC price.
- Yahoo supplies only the exact 09:30 New York one-minute opening bar; there is no intraday monitoring.
- FinanceDataReader daily candles must not be used for same-day opening-price execution.
- Quanters values are entered manually and stored per order date.
- Capital/Cash are Gold Toilet-specific and owner-scoped.
- No broker submission or fill recording is added.
- `httpx` is a runtime dependency for the Yahoo minute request.

---

### Task 1: Calculation and persistence domain

**Files:**
- Create: `backend/app/services/gold_toilet_order_service.py`
- Create: `backend/app/infrastructure/repositories/gold_toilet_orders.py`
- Modify: `backend/app/domain/models.py`
- Modify: `backend/app/db/migrations.py`
- Test: `backend/tests/test_gold_toilet_order_service.py`
- Test: `backend/tests/test_migrations.py`

**Interfaces:**
- Produces `calculate_gold_toilet_order(capital, cash, market_open, entry_percent, allocation_percent, loc_percent) -> GoldToiletCalculation`.
- Produces `GoldToiletOrderRepository.get_account`, `save_account`, `get_sheet`, and `save_sheet`.

- [ ] Write failing literal-expectation tests for cent rounding, LOC-based shared quantity, and insufficient-Cash warning.
- [ ] Run `pytest tests/test_gold_toilet_order_service.py -q` and confirm failure because the service does not exist.
- [ ] Implement the minimal calculation types and function, then rerun the focused tests.
- [ ] Write failing persistence and migration tests for the two owner-scoped tables.
- [ ] Add the SQLAlchemy models, repository, and SQLite migration 10, then rerun focused tests.

### Task 2: Opening-price resolution and authenticated API

**Files:**
- Create: `backend/app/dto/gold_toilet_orders.py`
- Create: `backend/app/api/routes_gold_toilet_orders.py`
- Modify: `backend/app/services/gold_toilet_order_service.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_gold_toilet_orders.py`

**Interfaces:**
- `GET /api/gold-toilet/order-sheet?order_date=YYYY-MM-DD` returns account, exact-date sheet, opening-price status, and calculation.
- `PUT /api/gold-toilet/account` stores positive Capital and non-negative Cash.
- `PUT /api/gold-toilet/order-sheet/{order_date}` stores only the manual percentages.
- `PUT /api/gold-toilet/order-sheet/{order_date}/manual-open` explicitly applies a manual price after the automatic open exists.
- `DELETE /api/gold-toilet/order-sheet/{order_date}/manual-open` restores the preserved automatic price.

- [ ] Write failing API tests for authentication, save/read behavior, automatic open snapshot, waiting state, manual override, and invalid percentages.
- [ ] Run `pytest tests/test_api_gold_toilet_orders.py -q` and confirm route failures.
- [ ] Add DTOs, provider injection boundary, service orchestration, routes, and router registration.
- [ ] Rerun the API tests and the Task 1 tests until green.

### Task 3: Dedicated React page

**Files:**
- Create: `frontend/src/api/goldToiletOrders.ts`
- Create: `frontend/src/pages/GoldToiletOrderPage.tsx`
- Create: `frontend/src/utils/goldToiletOrder.ts`
- Create: `frontend/src/utils/goldToiletOrder.test.ts`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- `shouldPollForOpen(orderDate, openStatus)` gates the five-second polling loop for both `waiting` and `failed` states.
- The page uses the three API functions and displays three large copyable results.

- [ ] Write failing Vitest tests for exact-date polling and copy-value formatting.
- [ ] Run `npm test -- --run src/utils/goldToiletOrder.test.ts` and confirm the missing-module failure.
- [ ] Add types, API client, utility, tab routing, page forms, polling, result cards, warnings, and responsive styles.
- [ ] Rerun the focused Vitest file and `npm run build`.

### Task 4: Full verification

**Files:**
- Review all files changed by Tasks 1-3.

**Interfaces:**
- Consumes the complete feature and produces verification evidence.

- [ ] Run `pytest -q` from `backend` and resolve every regression.
- [ ] Run `npm test -- --run` from `frontend` and resolve every regression.
- [ ] Run `npm run build` from `frontend` and resolve every TypeScript or bundling error.
- [ ] Review `git diff --check`, `git status --short`, and the complete diff against the design requirements.
