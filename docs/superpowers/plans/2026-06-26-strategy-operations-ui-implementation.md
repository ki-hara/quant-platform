# Strategy Operations UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve daily strategy operation by clarifying presets, enabling strategy archival, supporting Cash/Capital adjustments, limiting LOC ladders to 5 rows, and selecting LOC basis prices by market cutoff time.

**Architecture:** Keep the monolith structure and existing repository/service/DTO layering. Backend changes add small focused services for strategy archival, portfolio adjustments, market cutoff date selection, and LOC ladder calculation; frontend changes consume those APIs and reorganize existing pages without introducing a new state library.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, Python 3.12, pytest, React, TypeScript, Vite, lucide-react.

---

## File Structure

Backend files to modify:

- `backend/app/domain/models.py`: add `StrategyConfig.archived_at` and new `PortfolioAdjustment` model.
- `backend/app/main.py`: extend SQLite bootstrap for new columns/tables.
- `backend/app/infrastructure/repositories/strategies.py`: exclude archived configs from normal lists and add archive helpers.
- `backend/app/infrastructure/repositories/portfolios.py`: keep existing portfolio repository unchanged; `PortfolioAdjustmentService` writes adjustment rows directly because the query surface is small.
- `backend/app/dto/strategies.py`: expose `archived_at` and archive response shape.
- `backend/app/dto/portfolios.py`: create adjustment request/response DTOs.
- `backend/app/api/routes_strategies.py`: add `DELETE /api/strategy-configs/{config_id}`.
- `backend/app/api/routes_portfolios.py`: create portfolio adjustment endpoints.
- `backend/app/services/strategy_config_service.py`: archive strategy configs.
- `backend/app/services/portfolio_adjustment_service.py`: create focused service for Cash/Capital adjustments.
- `backend/app/services/market_session_service.py`: create focused service for market cutoff date selection.
- `backend/app/services/daily_plan_service.py`: use cutoff-aware basis date and return LOC calculation basis.
- `backend/app/services/chart_service.py`: align LOC chart line with cutoff-aware basis.
- `backend/app/strategy_engine/loc.py`: limit ladder orders to total 5.
- `backend/app/dto/trading_plan.py`: add LOC basis fields and cumulative amount to LOC order.

Backend tests to add or modify:

- `backend/tests/test_strategy_config_service.py`
- `backend/tests/test_api_strategies.py`
- `backend/tests/test_portfolio_adjustment_service.py`
- `backend/tests/test_api_portfolio_adjustments.py`
- `backend/tests/test_market_session_service.py`
- `backend/tests/test_daily_plan_service.py`
- `backend/tests/test_loc.py`

Frontend files to modify:

- `frontend/src/types/api.ts`: add archive, adjustment, LOC basis, and LOC order fields.
- `frontend/src/api/strategies.ts`: add delete/archive API function.
- `frontend/src/api/portfolios.ts`: create adjustment API functions.
- `frontend/src/components/SettingsForm.tsx`: add preset active state and split field sections.
- `frontend/src/pages/SettingsPage.tsx`: add strategy delete button and refresh behavior.
- `frontend/src/pages/TradesPage.tsx`: add capital adjustment form, LOC basis display, 5-row LOC list UI.
- `frontend/src/components/DailyPlanPanel.tsx`: show LOC calculation basis.
- `frontend/src/styles.css`: add responsive layout styles for preset controls, setting sections, LOC rows, and adjustment form.

---

### Task 1: Archive Strategy Configs

**Files:**
- Modify: `backend/app/domain/models.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/infrastructure/repositories/strategies.py`
- Modify: `backend/app/services/strategy_config_service.py`
- Modify: `backend/app/api/routes_strategies.py`
- Modify: `backend/app/dto/strategies.py`
- Test: `backend/tests/test_strategy_config_service.py`
- Test: `backend/tests/test_api_strategies.py`

- [ ] **Step 1: Write failing service tests**

Add these tests to `backend/tests/test_strategy_config_service.py`.

```python
from datetime import datetime

from app.services.strategy_config_service import StrategyConfigService


def test_archive_config_hides_it_from_owner_list(session):
    service = StrategyConfigService(session)
    config = service.create_config(
        "default",
        make_strategy_config_request(name="To archive", symbol="SOXL"),
    )

    archived = service.archive_config(config.id)

    assert archived.archived_at is not None
    assert config.id not in [row.id for row in service.list_configs("default")]


def test_archived_config_cannot_be_loaded_for_normal_use(session):
    service = StrategyConfigService(session)
    config = service.create_config(
        "default",
        make_strategy_config_request(name="Archived", symbol="SOXL"),
    )
    service.archive_config(config.id)

    try:
        service.get_config(config.id)
    except ValueError as exc:
        assert "not found" in str(exc).lower()
    else:
        raise AssertionError("Expected archived config to be hidden")
```

Add this helper to the same test file:

```python
from decimal import Decimal

from app.services.strategy_config_service import StrategyConfigCreateRequest
from app.strategy_engine.dynamic_wave import DynamicWaveStrategy


def make_strategy_config_request(name="Strategy", symbol="SOXL"):
    return StrategyConfigCreateRequest(
        name=name,
        strategy_type="dynamic_wave",
        symbol=symbol,
        initial_capital=Decimal("2000"),
        fee_rate=Decimal("0.07"),
        slippage_rate=Decimal("0"),
        settings_json=DynamicWaveStrategy.default_settings(),
    )
```

- [ ] **Step 2: Run service tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_strategy_config_service.py -q
```

Expected: failure because `archive_config` or `archived_at` does not exist.

- [ ] **Step 3: Add `archived_at` model field**

In `backend/app/domain/models.py`, add this field to `StrategyConfig` after `updated_at`.

```python
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
```

- [ ] **Step 4: Add SQLite bootstrap migration**

In `backend/app/main.py`, extend `ensure_sqlite_schema()` with a helper that adds the column only if missing.

```python
def _ensure_column(session: Session, table_name: str, column_name: str, ddl: str) -> None:
    columns = session.execute(text(f"PRAGMA table_info({table_name})")).mappings().all()
    if column_name not in {row["name"] for row in columns}:
        session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))
```

Call it inside the existing SQLite schema block:

```python
_ensure_column(session, "strategy_configs", "archived_at", "archived_at DATETIME")
```

- [ ] **Step 5: Update repository methods**

In `backend/app/infrastructure/repositories/strategies.py`, import `datetime` and filter archived configs.

```python
from datetime import datetime
```

Change `get` and `list_by_owner`:

```python
    def get(self, config_id: int, include_archived: bool = False) -> StrategyConfig | None:
        config = self.session.get(StrategyConfig, config_id)
        if config is None:
            return None
        if config.archived_at is not None and not include_archived:
            return None
        return config

    def list_by_owner(self, owner_id: str) -> list[StrategyConfig]:
        stmt = (
            select(StrategyConfig)
            .where(StrategyConfig.owner_id == owner_id, StrategyConfig.archived_at.is_(None))
            .order_by(StrategyConfig.created_at, StrategyConfig.id)
        )
        return list(self.session.scalars(stmt))

    def archive(self, config: StrategyConfig) -> StrategyConfig:
        config.archived_at = datetime.utcnow()
        return self.save(config)
```

- [ ] **Step 6: Add service archive method**

In `backend/app/services/strategy_config_service.py`, add:

```python
    def archive_config(self, config_id: int) -> StrategyConfig:
        try:
            config = self.configs.get(config_id)
            if config is None:
                raise ValueError(f"Strategy config not found: {config_id}")
            archived = self.configs.archive(config)
            self.session.commit()
            return archived
        except Exception:
            self.session.rollback()
            raise
```

- [ ] **Step 7: Add API route**

In `backend/app/api/routes_strategies.py`, add:

```python
@router.delete("/strategy-configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_strategy_config(config_id: int, session: SessionDep) -> None:
    try:
        StrategyConfigService(session).archive_config(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
```

- [ ] **Step 8: Add DTO field**

In `backend/app/dto/strategies.py`, add `archived_at` to `StrategyConfigResponseDto`.

```python
    archived_at: datetime | None = None
```

- [ ] **Step 9: Run backend tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_strategy_config_service.py tests/test_api_strategies.py -q
```

Expected: pass.

- [ ] **Step 10: Commit**

```powershell
git add backend/app/domain/models.py backend/app/main.py backend/app/infrastructure/repositories/strategies.py backend/app/services/strategy_config_service.py backend/app/api/routes_strategies.py backend/app/dto/strategies.py backend/tests/test_strategy_config_service.py backend/tests/test_api_strategies.py
git commit -m "feat: archive strategy configs"
```

---

### Task 2: Portfolio Cash and Capital Adjustments

**Files:**
- Modify: `backend/app/domain/models.py`
- Modify: `backend/app/main.py`
- Create: `backend/app/dto/portfolios.py`
- Create: `backend/app/services/portfolio_adjustment_service.py`
- Create: `backend/app/api/routes_portfolios.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_portfolio_adjustment_service.py`
- Test: `backend/tests/test_api_portfolio_adjustments.py`

- [ ] **Step 1: Write failing service tests**

Create `backend/tests/test_portfolio_adjustment_service.py`.

```python
from decimal import Decimal

from app.services.portfolio_adjustment_service import PortfolioAdjustmentRequest, PortfolioAdjustmentService
from app.services.strategy_config_service import StrategyConfigService


def test_adjustment_updates_cash_and_capital(session):
    config = StrategyConfigService(session).create_config(
        "default",
        make_strategy_config_request(initial_capital=Decimal("1000")),
    )

    adjustment = PortfolioAdjustmentService(session).create_adjustment(
        config.id,
        PortfolioAdjustmentRequest(
            adjustment_date=date(2026, 6, 26),
            cash_delta=Decimal("100"),
            capital_delta=Decimal("50"),
            memo="deposit and strategy increase",
        ),
    )

    assert adjustment.cash_delta == Decimal("100")
    assert adjustment.capital_delta == Decimal("50")
    portfolio = adjustment.strategy_config.live_portfolio
    assert portfolio.cash == Decimal("1100.000000")
    assert portfolio.capital == Decimal("1050.000000")


def test_adjustment_rejects_negative_cash(session):
    config = StrategyConfigService(session).create_config(
        "default",
        make_strategy_config_request(initial_capital=Decimal("1000")),
    )

    try:
        PortfolioAdjustmentService(session).create_adjustment(
            config.id,
            PortfolioAdjustmentRequest(
                adjustment_date=date(2026, 6, 26),
                cash_delta=Decimal("-1001"),
                capital_delta=Decimal("0"),
                memo="too much withdrawal",
            ),
        )
    except ValueError as exc:
        assert "cash cannot be negative" in str(exc).lower()
    else:
        raise AssertionError("Expected negative cash rejection")
```

Add imports and helper:

```python
from datetime import date

from tests.test_strategy_config_service import make_strategy_config_request
```

- [ ] **Step 2: Run tests and verify failure**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_portfolio_adjustment_service.py -q
```

Expected: import failure because service does not exist.

- [ ] **Step 3: Add model**

In `backend/app/domain/models.py`, add relationship to `StrategyConfig`:

```python
    portfolio_adjustments: Mapped[list["PortfolioAdjustment"]] = relationship(back_populates="strategy_config")
```

Add model after `LivePortfolio`.

```python
class PortfolioAdjustment(Base):
    __tablename__ = "portfolio_adjustments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    strategy_config_id: Mapped[int] = mapped_column(
        ForeignKey("strategy_configs.id"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    cash_delta: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    capital_delta: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    memo: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    strategy_config: Mapped[StrategyConfig] = relationship(back_populates="portfolio_adjustments")
```

- [ ] **Step 4: Add SQLite table bootstrap**

In `backend/app/main.py`, add:

```python
session.execute(
    text(
        """
        CREATE TABLE IF NOT EXISTS portfolio_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_config_id INTEGER NOT NULL,
            date DATE NOT NULL,
            cash_delta NUMERIC(18, 6) NOT NULL,
            capital_delta NUMERIC(18, 6) NOT NULL,
            memo VARCHAR(500),
            created_at DATETIME NOT NULL,
            FOREIGN KEY(strategy_config_id) REFERENCES strategy_configs (id)
        )
        """
    )
)
```

- [ ] **Step 5: Create DTOs**

Create `backend/app/dto/portfolios.py`.

```python
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PortfolioAdjustmentCreateDto(BaseModel):
    date: date
    cash_delta: Decimal
    capital_delta: Decimal
    memo: str | None = None


class PortfolioAdjustmentResponseDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    strategy_config_id: int
    date: date
    cash_delta: Decimal
    capital_delta: Decimal
    memo: str | None
    created_at: datetime
```

- [ ] **Step 6: Create service**

Create `backend/app/services/portfolio_adjustment_service.py`.

```python
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.models import PortfolioAdjustment
from app.infrastructure.repositories.portfolios import PortfolioRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.strategy_engine.loc import MONEY_QUANT


@dataclass(frozen=True)
class PortfolioAdjustmentRequest:
    adjustment_date: date
    cash_delta: Decimal
    capital_delta: Decimal
    memo: str | None = None


class PortfolioAdjustmentService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.configs = StrategyConfigRepository(session)
        self.portfolios = PortfolioRepository(session)

    def list_adjustments(self, config_id: int) -> list[PortfolioAdjustment]:
        self._get_config(config_id)
        return list(
            self.session.query(PortfolioAdjustment)
            .filter(PortfolioAdjustment.strategy_config_id == config_id)
            .order_by(PortfolioAdjustment.date.desc(), PortfolioAdjustment.id.desc())
        )

    def create_adjustment(self, config_id: int, request: PortfolioAdjustmentRequest) -> PortfolioAdjustment:
        try:
            config = self._get_config(config_id)
            portfolio = self.portfolios.get_by_config(config_id)
            if portfolio is None:
                portfolio = self.portfolios.create_for_config(config)
            next_cash = (portfolio.cash + request.cash_delta).quantize(MONEY_QUANT)
            next_capital = (portfolio.capital + request.capital_delta).quantize(MONEY_QUANT)
            if next_cash < 0:
                raise ValueError("Cash cannot be negative after adjustment.")
            if next_capital < 0:
                raise ValueError("Capital cannot be negative after adjustment.")
            portfolio.cash = next_cash
            portfolio.capital = next_capital
            adjustment = PortfolioAdjustment(
                strategy_config_id=config_id,
                date=request.adjustment_date,
                cash_delta=request.cash_delta.quantize(MONEY_QUANT),
                capital_delta=request.capital_delta.quantize(MONEY_QUANT),
                memo=request.memo,
            )
            self.session.add(adjustment)
            self.session.commit()
            self.session.refresh(adjustment)
            return adjustment
        except Exception:
            self.session.rollback()
            raise

    def _get_config(self, config_id: int):
        config = self.configs.get(config_id)
        if config is None:
            raise ValueError(f"Strategy config not found: {config_id}")
        return config
```

- [ ] **Step 7: Add routes and include router**

Create `backend/app/api/routes_portfolios.py`.

```python
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.dto.portfolios import PortfolioAdjustmentCreateDto, PortfolioAdjustmentResponseDto
from app.services.portfolio_adjustment_service import PortfolioAdjustmentRequest, PortfolioAdjustmentService


router = APIRouter(prefix="/api/strategy-configs", tags=["portfolios"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/{config_id}/portfolio-adjustments", response_model=list[PortfolioAdjustmentResponseDto])
def list_portfolio_adjustments(config_id: int, session: SessionDep) -> object:
    try:
        return PortfolioAdjustmentService(session).list_adjustments(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{config_id}/portfolio-adjustments",
    response_model=PortfolioAdjustmentResponseDto,
    status_code=status.HTTP_201_CREATED,
)
def create_portfolio_adjustment(
    config_id: int,
    request: PortfolioAdjustmentCreateDto,
    session: SessionDep,
) -> object:
    try:
        return PortfolioAdjustmentService(session).create_adjustment(
            config_id,
            PortfolioAdjustmentRequest(
                adjustment_date=request.date,
                cash_delta=request.cash_delta,
                capital_delta=request.capital_delta,
                memo=request.memo,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
```

In `backend/app/main.py`, import and include:

```python
from app.api.routes_portfolios import router as portfolios_router
```

```python
app.include_router(portfolios_router)
```

- [ ] **Step 8: Run tests**

Create `backend/tests/test_api_portfolio_adjustments.py` before running the command.

```python
from datetime import date
from decimal import Decimal

from app.services.strategy_config_service import StrategyConfigService
from tests.test_strategy_config_service import make_strategy_config_request


def test_create_portfolio_adjustment_api_updates_portfolio(client, session):
    config = StrategyConfigService(session).create_config(
        "default",
        make_strategy_config_request(initial_capital=Decimal("1000")),
    )

    response = client.post(
        f"/api/strategy-configs/{config.id}/portfolio-adjustments",
        json={
            "date": "2026-06-26",
            "cash_delta": "100",
            "capital_delta": "50",
            "memo": "deposit",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["cash_delta"] == "100.000000"
    assert body["capital_delta"] == "50.000000"


def test_list_portfolio_adjustments_api(client, session):
    config = StrategyConfigService(session).create_config(
        "default",
        make_strategy_config_request(initial_capital=Decimal("1000")),
    )
    client.post(
        f"/api/strategy-configs/{config.id}/portfolio-adjustments",
        json={
            "date": "2026-06-26",
            "cash_delta": "100",
            "capital_delta": "100",
            "memo": "deposit",
        },
    )

    response = client.get(f"/api/strategy-configs/{config.id}/portfolio-adjustments")

    assert response.status_code == 200
    assert len(response.json()) == 1
```

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_portfolio_adjustment_service.py tests/test_api_portfolio_adjustments.py -q
```

Expected: pass.

- [ ] **Step 9: Commit**

```powershell
git add backend/app/domain/models.py backend/app/main.py backend/app/dto/portfolios.py backend/app/services/portfolio_adjustment_service.py backend/app/api/routes_portfolios.py backend/tests/test_portfolio_adjustment_service.py backend/tests/test_api_portfolio_adjustments.py
git commit -m "feat: add portfolio adjustments"
```

---

### Task 3: Market Cutoff-Aware LOC Basis Price

**Files:**
- Create: `backend/app/services/market_session_service.py`
- Modify: `backend/app/services/daily_plan_service.py`
- Modify: `backend/app/services/chart_service.py`
- Modify: `backend/app/dto/trading_plan.py`
- Test: `backend/tests/test_market_session_service.py`
- Test: `backend/tests/test_daily_plan_service.py`

- [ ] **Step 1: Write failing market session tests**

Create `backend/tests/test_market_session_service.py`.

```python
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.services.market_session_service import latest_confirmed_market_date


def test_us_symbol_before_cutoff_uses_previous_market_date():
    now = datetime(2026, 6, 26, 1, 0, tzinfo=ZoneInfo("Asia/Seoul"))

    assert latest_confirmed_market_date("SOXL", now) == date(2026, 6, 24)


def test_us_symbol_after_cutoff_uses_current_us_market_date():
    now = datetime(2026, 6, 26, 5, 40, tzinfo=ZoneInfo("Asia/Seoul"))

    assert latest_confirmed_market_date("SOXL", now) == date(2026, 6, 25)


def test_korean_symbol_before_cutoff_uses_previous_date():
    now = datetime(2026, 6, 26, 15, 20, tzinfo=ZoneInfo("Asia/Seoul"))

    assert latest_confirmed_market_date("005930.KS", now) == date(2026, 6, 25)


def test_korean_symbol_after_cutoff_uses_today():
    now = datetime(2026, 6, 26, 15, 50, tzinfo=ZoneInfo("Asia/Seoul"))

    assert latest_confirmed_market_date("005930.KS", now) == date(2026, 6, 26)
```

- [ ] **Step 2: Run tests and verify failure**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_market_session_service.py -q
```

Expected: import failure because `market_session_service` does not exist.

- [ ] **Step 3: Implement market session service**

Create `backend/app/services/market_session_service.py`.

```python
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


US_CUTOFF = time(16, 30)
KR_CUTOFF = time(15, 40)


def latest_confirmed_market_date(symbol: str, now: datetime | None = None) -> date:
    current = now or datetime.now(ZoneInfo("Asia/Seoul"))
    if _is_korean_symbol(symbol):
        local = current.astimezone(ZoneInfo("Asia/Seoul"))
        basis = local.date() if local.time() >= KR_CUTOFF else local.date() - timedelta(days=1)
    else:
        local = current.astimezone(ZoneInfo("America/New_York"))
        basis = local.date() if local.time() >= US_CUTOFF else local.date() - timedelta(days=1)
    return _previous_weekday(basis)


def _is_korean_symbol(symbol: str) -> bool:
    upper = symbol.upper()
    return upper.endswith(".KS") or upper.endswith(".KQ")


def _previous_weekday(value: date) -> date:
    while value.weekday() >= 5:
        value = value - timedelta(days=1)
    return value
```

- [ ] **Step 4: Add DTO basis fields**

In `backend/app/dto/trading_plan.py`, add fields to `DailyPlanDto`.

```python
    loc_basis_date: date | None
    loc_basis_close: Decimal | None
    loc_formula: str | None
```

- [ ] **Step 5: Update daily plan service**

In `backend/app/services/daily_plan_service.py`, import:

```python
from datetime import datetime
from app.services.market_session_service import latest_confirmed_market_date
```

Change the method signature:

```python
    def get_daily_plan(self, config_id: int, today: date, now: datetime | None = None) -> DailyPlanDto:
```

Inside `get_daily_plan`, replace `latest_price_on_or_before(..., today)` with:

```python
        basis_date = latest_confirmed_market_date(config.symbol, now)
```

then:

```python
        latest_price = self.market_prices.latest_price_on_or_before(
            settings.market_data_provider,
            config.symbol,
            basis_date,
        )
```

When returning `DailyPlanDto`, set:

```python
            loc_basis_date=data_as_of,
            loc_basis_close=previous_close,
            loc_formula=(
                f"{previous_close} * (1 + {buy_threshold} / 100) = {loc_plan.limit_price}"
                if previous_close is not None
                else None
            ),
```

The route keeps calling `get_daily_plan(config_id, today or date.today())`, so production uses the current time.

- [ ] **Step 6: Add daily plan regression test**

In `backend/tests/test_daily_plan_service.py`, add a test that inserts SOXL prices for 2026-06-24 and 2026-06-25, then calls `get_daily_plan(config.id, date(2026, 6, 26), now=datetime(2026, 6, 26, 1, 0, tzinfo=ZoneInfo("Asia/Seoul")))`.

Expected assertions:

```python
assert plan.loc_basis_date == date(2026, 6, 24)
assert plan.previous_close == Decimal("229.570000")
assert plan.LOC.limit_price == Decimal("236.457100")
```

- [ ] **Step 7: Update chart service**

In `backend/app/services/chart_service.py`, select LOC basis price using the same service instead of latest saved price for the request date.

```python
basis_date = latest_confirmed_market_date(config.symbol)
latest_price = self.market_prices.latest_price_on_or_before(
    settings.market_data_provider,
    config.symbol,
    basis_date,
)
```

- [ ] **Step 8: Run tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_market_session_service.py tests/test_daily_plan_service.py tests/test_chart_service.py -q
```

Expected: pass.

- [ ] **Step 9: Commit**

```powershell
git add backend/app/services/market_session_service.py backend/app/services/daily_plan_service.py backend/app/services/chart_service.py backend/app/dto/trading_plan.py backend/tests/test_market_session_service.py backend/tests/test_daily_plan_service.py backend/tests/test_chart_service.py
git commit -m "fix: use market cutoff for LOC basis"
```

---

### Task 4: Limit LOC Ladder to 5 Rows

**Files:**
- Modify: `backend/app/strategy_engine/loc.py`
- Modify: `backend/app/dto/trading_plan.py`
- Test: `backend/tests/test_loc.py`

- [ ] **Step 1: Write failing LOC ladder tests**

Add to `backend/tests/test_loc.py`.

```python
from decimal import Decimal

from app.strategy_engine.loc import calculate_loc_plan


def test_loc_ladder_never_exceeds_five_orders():
    plan = calculate_loc_plan(
        previous_close=Decimal("100"),
        capital=Decimal("10000000"),
        cash=Decimal("10000000"),
        fee_rate=Decimal("0"),
        split_count=7,
        buy_threshold_percent=Decimal("3"),
        open_position_count=0,
    )

    assert len(plan.orders) <= 5
    assert plan.orders[0].step == 1
    assert plan.orders[-1].limit_price >= Decimal("72.100000")


def test_loc_ladder_cumulative_amount_stays_within_allocation():
    plan = calculate_loc_plan(
        previous_close=Decimal("229.570007"),
        capital=Decimal("10000000"),
        cash=Decimal("10000000"),
        fee_rate=Decimal("0"),
        split_count=7,
        buy_threshold_percent=Decimal("3"),
        open_position_count=0,
    )

    for order in plan.orders:
        assert order.cumulative_amount <= plan.allocation
```

- [ ] **Step 2: Run tests and verify failure**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_loc.py -q
```

Expected: failure because current ladder returns up to 11 orders and no cumulative amount field exists.

- [ ] **Step 3: Update LOC order model**

In `backend/app/strategy_engine/loc.py`, change constant:

```python
MAX_LOC_ORDER_ROWS = 5
MAX_LADDER_EXTRA_ORDERS = MAX_LOC_ORDER_ROWS - 1
```

Add field:

```python
    cumulative_amount: Decimal
```

Set it on first order:

```python
            cumulative_amount=_money(base_limit * Decimal(base_quantity)),
```

Set it on additional orders:

```python
                cumulative_amount=_money(trigger_price * Decimal(target_total)),
```

- [ ] **Step 4: Update DTO**

In `backend/app/dto/trading_plan.py`, add to `LocOrderDto`:

```python
    cumulative_amount: Decimal
```

Keep `compressed` for backward compatibility, but the frontend will stop displaying it.

- [ ] **Step 5: Run tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_loc.py tests/test_daily_plan_service.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/strategy_engine/loc.py backend/app/dto/trading_plan.py backend/tests/test_loc.py
git commit -m "fix: limit LOC ladder rows"
```

---

### Task 5: Frontend Settings Presets and Strategy Delete

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/strategies.ts`
- Modify: `frontend/src/components/SettingsForm.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Update frontend API types**

In `frontend/src/types/api.ts`, add:

```ts
  archived_at: ISODateTime | null;
```

to `StrategyConfig`.

- [ ] **Step 2: Add delete API**

In `frontend/src/api/client.ts`, add:

```ts
export async function apiDelete(path: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method: "DELETE" });
  if (!response.ok) throw new Error(await errorMessage(response));
}
```

In `frontend/src/api/strategies.ts`, import `apiDelete`.

```ts
import { apiDelete, apiGet, apiPost, apiPut } from "./client";
```

Add:

```ts
export async function deleteStrategyConfig(configId: number): Promise<void> {
  await apiDelete(`/api/strategy-configs/${configId}`);
}
```

- [ ] **Step 3: Add preset active-state helpers**

In `frontend/src/components/SettingsForm.tsx`, add:

```ts
const presetLabels = ["적극투자형", "공격투자형"] as const;
type PresetLabel = (typeof presetLabels)[number] | "사용자 설정";

function presetForSettings(settings: Record<string, FieldValue>): PresetLabel {
  const matched = investmentPresets.find((preset) =>
    Object.entries(preset.values).every(([key, value]) => settings[key] === value),
  );
  return matched?.label as PresetLabel ?? "사용자 설정";
}
```

Use it in the component:

```ts
const activePreset = presetForSettings({ ...defaultSettingsFromFields(fields), ...settings });
```

Add a `사용자 설정` read-only pill next to the two buttons.

- [ ] **Step 4: Split settings fields into sections**

Add helper:

```ts
function sectionForField(key: string): "rsi" | "safe" | "aggressive" {
  if (key.startsWith("safe.")) return "safe";
  if (key.startsWith("aggressive.")) return "aggressive";
  return "rsi";
}
```

Render three groups with Korean headings:

```tsx
<SettingSection title="RSI / 투자금 갱신" fields={visibleFields.filter((field) => sectionForField(field.key) === "rsi")} />
<SettingSection title="안전모드" fields={visibleFields.filter((field) => sectionForField(field.key) === "safe")} />
<SettingSection title="공세모드" fields={visibleFields.filter((field) => sectionForField(field.key) === "aggressive")} />
```

Keep the existing field rendering logic inside `SettingSection`.

- [ ] **Step 5: Add delete action on settings page**

In `frontend/src/pages/SettingsPage.tsx`, import:

```ts
import { deleteStrategyConfig } from "../api/strategies";
import { Trash2 } from "lucide-react";
```

Add handler:

```ts
async function handleDeleteConfig(config: StrategyConfig) {
  if (!window.confirm(`${config.name} / ${config.symbol} 전략을 삭제할까요? 거래내역은 보존됩니다.`)) return;
  try {
    setSaving(true);
    setError("");
    await deleteStrategyConfig(config.id);
    setConfigs((current) => current.filter((row) => row.id !== config.id));
    if (editingId === config.id) setEditingId(null);
    setMessage("전략을 삭제했습니다. 기존 거래내역은 보존됩니다.");
  } catch (caught) {
    setError(errorMessage(caught));
  } finally {
    setSaving(false);
  }
}
```

Add a table action column with a trash icon button.

- [ ] **Step 6: Add CSS**

In `frontend/src/styles.css`, add classes:

```css
.preset-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.preset-row button.is-active { border-color: #2563eb; background: #eff6ff; color: #1d4ed8; }
.setting-sections { display: grid; gap: 16px; }
.setting-section { border-top: 1px solid var(--border); padding-top: 14px; }
.setting-section h3 { margin: 0 0 10px; font-size: 15px; }
.status-pill.is-muted { background: #f3f4f6; color: #4b5563; }
```

- [ ] **Step 7: Build frontend**

```powershell
npm run build
```

Expected: TypeScript and Vite build pass.

- [ ] **Step 8: Commit**

```powershell
git add frontend/src/types/api.ts frontend/src/api/strategies.ts frontend/src/api/client.ts frontend/src/components/SettingsForm.tsx frontend/src/pages/SettingsPage.tsx frontend/src/styles.css
git commit -m "feat: improve strategy settings controls"
```

---

### Task 6: Frontend Portfolio Adjustments and LOC Evidence

**Files:**
- Modify: `frontend/src/types/api.ts`
- Create: `frontend/src/api/portfolios.ts`
- Modify: `frontend/src/pages/TradesPage.tsx`
- Modify: `frontend/src/components/DailyPlanPanel.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Add frontend types**

In `frontend/src/types/api.ts`, add:

```ts
export interface PortfolioAdjustment {
  id: number;
  strategy_config_id: number;
  date: ISODate;
  cash_delta: DecimalString;
  capital_delta: DecimalString;
  memo: string | null;
  created_at: ISODateTime;
}

export interface PortfolioAdjustmentCreateRequest {
  date: ISODate;
  cash_delta: DecimalString;
  capital_delta: DecimalString;
  memo?: string | null;
}
```

Add fields to `DailyPlan`:

```ts
  loc_basis_date: ISODate | null;
  loc_basis_close: DecimalString | null;
  loc_formula: string | null;
```

Add to `LocOrder`:

```ts
  cumulative_amount: DecimalString;
```

- [ ] **Step 2: Add adjustment API**

Create `frontend/src/api/portfolios.ts`.

```ts
import { apiGet, apiPost } from "./client";
import type { PortfolioAdjustment, PortfolioAdjustmentCreateRequest } from "../types/api";

export function listPortfolioAdjustments(configId: number): Promise<PortfolioAdjustment[]> {
  return apiGet<PortfolioAdjustment[]>(`/api/strategy-configs/${configId}/portfolio-adjustments`);
}

export function createPortfolioAdjustment(
  configId: number,
  request: PortfolioAdjustmentCreateRequest,
): Promise<PortfolioAdjustment> {
  return apiPost<PortfolioAdjustment>(`/api/strategy-configs/${configId}/portfolio-adjustments`, request);
}
```

- [ ] **Step 3: Add adjustment form state**

In `frontend/src/pages/TradesPage.tsx`, import APIs and type.

```ts
import { createPortfolioAdjustment, listPortfolioAdjustments } from "../api/portfolios";
import type { PortfolioAdjustment } from "../types/api";
```

Add state:

```ts
const [adjustments, setAdjustments] = useState<PortfolioAdjustment[]>([]);
const [adjustBoth, setAdjustBoth] = useState(true);
const [adjustmentForm, setAdjustmentForm] = useState({
  date: todayIso(),
  amount: "",
  cash_delta: "",
  capital_delta: "",
  memo: "",
});
```

Include `listPortfolioAdjustments(configId)` in `loadRows`.

- [ ] **Step 4: Add adjustment submit handler**

In `TradesPage`, add:

```ts
async function handleAdjustmentSubmit(event: FormEvent<HTMLFormElement>) {
  event.preventDefault();
  if (!selectedId) return;
  const cashDelta = adjustBoth ? adjustmentForm.amount : adjustmentForm.cash_delta;
  const capitalDelta = adjustBoth ? adjustmentForm.amount : adjustmentForm.capital_delta;
  try {
    setSaving(true);
    setError("");
    await createPortfolioAdjustment(selectedId, {
      date: adjustmentForm.date,
      cash_delta: cashDelta || "0",
      capital_delta: capitalDelta || "0",
      memo: adjustmentForm.memo.trim() || null,
    });
    setMessage("자본 조정을 저장했습니다.");
    setAdjustmentForm({ date: todayIso(), amount: "", cash_delta: "", capital_delta: "", memo: "" });
    await loadRows(selectedId);
  } catch (caught) {
    setError(errorMessage(caught));
  } finally {
    setSaving(false);
  }
}
```

- [ ] **Step 5: Render adjustment panel**

Add a panel near the manual trade form:

```tsx
<section className="panel">
  <div className="panel-header">
    <div>
      <h2>자본 조정</h2>
      <span>현금 입출금과 전략 기준금 조정을 기록합니다.</span>
    </div>
  </div>
  <form className="form-stack" onSubmit={handleAdjustmentSubmit}>
    <label>날짜<input type="date" value={adjustmentForm.date} onChange={(event) => setAdjustmentForm((current) => ({ ...current, date: event.target.value }))} /></label>
    <label className="checkbox-row"><input type="checkbox" checked={adjustBoth} onChange={(event) => setAdjustBoth(event.target.checked)} /> Cash와 Capital을 같은 금액만큼 조정</label>
    {adjustBoth ? (
      <label>조정 금액<input value={adjustmentForm.amount} inputMode="decimal" onChange={(event) => setAdjustmentForm((current) => ({ ...current, amount: event.target.value }))} /></label>
    ) : (
      <>
        <label>Cash 조정액<input value={adjustmentForm.cash_delta} inputMode="decimal" onChange={(event) => setAdjustmentForm((current) => ({ ...current, cash_delta: event.target.value }))} /></label>
        <label>Capital 조정액<input value={adjustmentForm.capital_delta} inputMode="decimal" onChange={(event) => setAdjustmentForm((current) => ({ ...current, capital_delta: event.target.value }))} /></label>
      </>
    )}
    <label>메모<input value={adjustmentForm.memo} onChange={(event) => setAdjustmentForm((current) => ({ ...current, memo: event.target.value }))} /></label>
    <button type="submit" disabled={!selectedId || saving}>저장</button>
  </form>
</section>
```

- [ ] **Step 6: Render LOC calculation evidence**

In `frontend/src/components/DailyPlanPanel.tsx`, add rows:

```tsx
<div>
  <dt>LOC 기준일</dt>
  <dd>{plan?.loc_basis_date ?? "-"}</dd>
</div>
<div>
  <dt>기준 종가</dt>
  <dd>{formatMoney(plan?.loc_basis_close, plan?.symbol)}</dd>
</div>
<div className="detail-grid-wide">
  <dt>계산식</dt>
  <dd>{plan?.loc_formula ?? "-"}</dd>
</div>
```

In `TradesPage`, replace the LOC order text with:

```tsx
<div className="loc-order-list">
  {plan.LOC.orders.slice(0, 5).map((order) => (
    <div className="loc-order-row" key={order.step}>
      <span>{order.step}차 LOC</span>
      <strong>{formatMoney(order.limit_price)} x {order.quantity}주</strong>
      <small>누적 {order.cumulative_quantity}주 / {formatMoney(order.cumulative_amount)}</small>
    </div>
  ))}
</div>
```

Do not render `order.compressed`.

- [ ] **Step 7: Add responsive CSS**

In `frontend/src/styles.css`, add:

```css
.loc-order-list { display: grid; gap: 8px; margin-top: 10px; }
.loc-order-row { display: grid; grid-template-columns: minmax(70px, auto) minmax(130px, 1fr) minmax(150px, auto); gap: 8px; align-items: center; }
.detail-grid-wide { grid-column: 1 / -1; }
.checkbox-row { display: flex; flex-direction: row; gap: 8px; align-items: center; }
@media (max-width: 720px) {
  .loc-order-row { grid-template-columns: 1fr; align-items: start; }
}
```

- [ ] **Step 8: Build frontend**

```powershell
npm run build
```

Expected: pass.

- [ ] **Step 9: Commit**

```powershell
git add frontend/src/types/api.ts frontend/src/api/portfolios.ts frontend/src/pages/TradesPage.tsx frontend/src/components/DailyPlanPanel.tsx frontend/src/styles.css
git commit -m "feat: show LOC evidence and capital adjustments"
```

---

### Task 7: End-to-End Verification

**Files:**
- No planned source edits unless verification finds a bug.

- [ ] **Step 1: Run backend checks**

```powershell
cd backend
$env:TMP='C:\Users\starc\Documents\퀀트 투자\.tmp'
$env:TEMP='C:\Users\starc\Documents\퀀트 투자\.tmp'
New-Item -ItemType Directory -Force -Path $env:TMP | Out-Null
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
```

Expected: all tests pass and Ruff reports `All checks passed!`.

- [ ] **Step 2: Run frontend build**

```powershell
cd frontend
npm run build
```

Expected: TypeScript and Vite build pass.

- [ ] **Step 3: Restart backend**

```powershell
$connections = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($pidValue in $connections) { Stop-Process -Id $pidValue -Force }
Start-Sleep -Seconds 1
Start-Process -FilePath '.\.venv\Scripts\python.exe' -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory 'C:\Users\starc\Documents\퀀트 투자\backend' -WindowStyle Hidden
```

- [ ] **Step 4: Verify LOC basis through API**

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/strategy-configs/2/daily-plan?today=2026-06-26' | ConvertTo-Json -Depth 8
```

Expected while before US cutoff: `loc_basis_date` is `2026-06-24` and LOC price is based on `229.57`.

- [ ] **Step 5: Browser verification**

Open `http://127.0.0.1:5173/` and verify:

- 설정 페이지 shows active preset clearly.
- 설정 페이지 separates `RSI / 투자금 갱신`, `안전모드`, `공세모드`.
- 설정 목록 has a delete icon and archived strategies disappear after confirmation.
- 거래/포지션 page shows `자본 조정`.
- LOC orders show no more than 5 rows and no `축약` text.
- LOC calculation evidence shows basis date, basis close, and formula.
- Narrow viewport does not overlap LOC order text.

- [ ] **Step 6: Final status**

Run:

```powershell
git status --short
```

Expected: only untracked `rsi/` remains unless the user asks to commit additional generated files.
