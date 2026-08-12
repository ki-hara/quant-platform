# Resilient Regular Open Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture SOXL's regular-session open within seconds using independently validated CNBC/NYSE Arca and Finnhub quotes, without allowing one bad provider to block progress.

**Architecture:** Introduce a provider-neutral quote contract and focused CNBC, Finnhub, and composite provider modules. The synchronous composite executes both network lookups concurrently, validates provider responses independently, then selects a source using deterministic bounded-disagreement rules; the existing collector persists both price and source.

**Tech Stack:** Python 3.12, FastAPI, httpx, concurrent.futures, SQLAlchemy, pytest, React, TypeScript, Vitest.

## Global Constraints

- Start polling five seconds before 09:30 America/New_York and poll every two seconds.
- Never accept a quote before the requested regular session begins.
- CNBC/NYSE Arca is preferred when valid; Finnhub is an independent fallback.
- Finnhub uses optional `QUANT_FINNHUB_API_KEY`, never exposed to the frontend or logs.
- Yahoo must not finalize new Gold Toilet automatic opening prices.
- Existing manual-open recovery and historical Yahoo source values remain compatible.

---

### Task 1: Provider-neutral contracts and provider parsers

**Files:**
- Create: `backend/app/infrastructure/market_data/regular_open.py`
- Create: `backend/app/infrastructure/market_data/cnbc_regular_open_provider.py`
- Create: `backend/app/infrastructure/market_data/finnhub_regular_open_provider.py`
- Create: `backend/tests/test_cnbc_regular_open_provider.py`
- Create: `backend/tests/test_finnhub_regular_open_provider.py`
- Modify: imports currently taking contracts from `yahoo_regular_open_provider.py`

**Interfaces:**
- Produces: `RegularSessionOpen(symbol, session_date, price, high, low, bar_time, source)` and `RegularOpenLookup(quote, failure_reason)`.
- Produces: `CnbcRegularOpenProvider.get_open(symbol, session_date)` and `FinnhubRegularOpenProvider.get_open(symbol, session_date)`.

- [ ] Write CNBC contract tests using a fixture whose `open` is `147.30`, market status is regular, timestamp is after 09:30, and source is `cnbc_us_quote`; add rejection cases for pre-open, wrong symbol, and impossible OHLC.
- [ ] Run `cd backend; uv run pytest tests/test_cnbc_regular_open_provider.py -q` and verify failure because the provider module does not exist.
- [ ] Implement provider-neutral dataclasses, common session/OHLC validation, and the CNBC parser/client with a five-second timeout.
- [ ] Run the CNBC tests and verify they pass.
- [ ] Write Finnhub tests for `{o,h,l,t}` parsing, missing API key, stale timestamp, and impossible OHLC.
- [ ] Run `cd backend; uv run pytest tests/test_finnhub_regular_open_provider.py -q` and verify failure because the provider module does not exist.
- [ ] Implement the Finnhub parser/client using the `X-Finnhub-Token` header and source `finnhub_us_quote`.
- [ ] Run both provider test files and verify they pass.

### Task 2: Concurrent composite and bounded arbitration

**Files:**
- Create: `backend/app/infrastructure/market_data/resilient_regular_open_provider.py`
- Create: `backend/tests/test_resilient_regular_open_provider.py`

**Interfaces:**
- Consumes: provider `get_open(symbol, session_date) -> RegularOpenLookup`.
- Produces: `ResilientRegularOpenProvider.get_open(symbol, session_date) -> RegularOpenLookup`.

- [ ] Write tests proving that valid CNBC returns immediately when Finnhub fails, valid Finnhub returns when CNBC fails, CNBC wins within `$0.05`, a larger first disagreement returns `opening_price_sources_disagree`, and the same disagreement on the next call selects CNBC.
- [ ] Run `cd backend; uv run pytest tests/test_resilient_regular_open_provider.py -q` and verify failure because the composite module does not exist.
- [ ] Implement parallel calls with `ThreadPoolExecutor`, provider exception isolation, five-cent comparison, and an in-memory disagreement signature keyed by symbol/session.
- [ ] Run the composite tests and verify they pass.

### Task 3: Persist the selected source and wire runtime configuration

**Files:**
- Modify: `backend/app/infrastructure/repositories/gold_toilet_orders.py`
- Modify: `backend/app/services/gold_toilet_open_collector.py`
- Modify: `backend/app/services/gold_toilet_order_interpreter.py`
- Modify: `backend/app/dto/gold_toilet_orders.py`
- Modify: `backend/app/api/routes_gold_toilet_orders.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/tests/test_gold_toilet_open_collector.py`
- Modify: `backend/tests/test_api_gold_toilet_orders.py`

**Interfaces:**
- `snapshot_provider_open(sheet, market_open, source, observed_at)` persists the provider source.
- `effective_open_source` accepts `manual`, `cnbc_us_quote`, `finnhub_us_quote`, and legacy `yahoo_1d_regular_session`.

- [ ] Update collector/API tests first to expect a quote's selected source and verify legacy Yahoo-labelled rows still serialize.
- [ ] Run the focused tests and verify failures at the repository signature/source assertions.
- [ ] Add optional `finnhub_api_key` settings, build the composite provider in one shared factory, wire it into lifespan and request dependencies, and change polling to two seconds.
- [ ] Pass `quote.source` into repository persistence and return the stored source from `_effective_open`.
- [ ] Run `cd backend; uv run pytest tests/test_gold_toilet_open_collector.py tests/test_api_gold_toilet_orders.py -q` and verify they pass.

### Task 4: Korean source labels and waiting copy

**Files:**
- Modify: `frontend/src/api/goldToiletOrders.ts`
- Modify: `frontend/src/pages/GoldToiletOrdersPage.tsx`
- Modify or create: matching frontend tests under `frontend/src`.

**Interfaces:**
- `sourceLabel()` maps new sources to `NYSE Arca 실시간 시세` and `Finnhub 미국 실시간 시세` while keeping manual and legacy Yahoo labels.

- [ ] Write or update a frontend test that renders each new source label and the provider-neutral waiting message.
- [ ] Run `cd frontend; npm test -- --run` and verify the new assertions fail.
- [ ] Expand the TypeScript source union and replace Yahoo/daily-candle-specific copy with real-time multi-provider copy.
- [ ] Run the frontend tests and verify they pass.

### Task 5: Deployment documentation and full verification

**Files:**
- Modify: `deploy/oci/production.env.example`

**Interfaces:**
- Documents: `QUANT_FINNHUB_API_KEY=<free Finnhub API key>` as optional redundancy.

- [ ] Add the optional environment variable without committing an actual secret.
- [ ] Run `cd backend; uv run ruff check .; uv run pytest -q`.
- [ ] Run `cd frontend; npm test -- --run; npm run build`.
- [ ] Run `git diff --check` and inspect `git status --short` to ensure only intended files changed.
- [ ] Commit the implementation with a focused feature message.
