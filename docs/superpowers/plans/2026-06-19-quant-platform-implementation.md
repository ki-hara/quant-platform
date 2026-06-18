# Quant Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working version of the quant strategy research and backtest platform with a separated FastAPI backend, React TypeScript frontend, SQLite persistence, Dynamic Wave Strategy, live signal execution support, backtesting, charts, CSV downloads, tests, Docker, and README.

**Architecture:** Use a modular monolith backend with clear internal boundaries: API, DTOs, services, domain, repositories, strategy engine, backtest engine, and infrastructure. Keep the frontend fully separated and consume REST APIs through typed client modules. Strategy logic is implemented once and reused by live signal calculation and backtests.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2, Pydantic 2, SQLite, pytest, React, TypeScript, Vite, Lightweight Charts, Docker Compose.

---

## Target File Structure

Create this structure from the empty repository:

```text
backend/
  app/
    __init__.py
    main.py
    api/
      __init__.py
      routes_backtests.py
      routes_dashboard.py
      routes_market_data.py
      routes_strategies.py
      routes_trades.py
    core/
      __init__.py
      config.py
      errors.py
    db/
      __init__.py
      base.py
      session.py
      seed.py
    domain/
      __init__.py
      models.py
      enums.py
      strategy.py
    dto/
      __init__.py
      backtests.py
      dashboard.py
      market_data.py
      strategies.py
      trades.py
    infrastructure/
      __init__.py
      market_data/
        __init__.py
        base.py
        finance_data_reader_provider.py
        cached_provider.py
      repositories/
        __init__.py
        backtests.py
        market_data.py
        portfolios.py
        strategies.py
        trades.py
    services/
      __init__.py
      backtest_service.py
      dashboard_service.py
      market_data_service.py
      signal_execution_service.py
      strategy_config_service.py
    strategy_engine/
      __init__.py
      base.py
      context.py
      dynamic_wave.py
      registry.py
    backtest_engine/
      __init__.py
      engine.py
      metrics.py
      simulator.py
  tests/
    conftest.py
    fixtures.py
    test_api_backtests.py
    test_api_dashboard.py
    test_backtest_engine.py
    test_dynamic_wave_strategy.py
    test_repositories.py
  Dockerfile
  pyproject.toml
frontend/
  src/
    api/
      client.ts
      backtests.ts
      dashboard.ts
      strategies.ts
      trades.ts
    components/
      BacktestChart.tsx
      MetricStrip.tsx
      SettingsForm.tsx
      SignalPanel.tsx
      Table.tsx
    pages/
      BacktestPage.tsx
      DashboardPage.tsx
      SettingsPage.tsx
      TradesPage.tsx
    types/
      api.ts
    App.tsx
    main.tsx
    styles.css
    vite-env.d.ts
  Dockerfile
  index.html
  package.json
  tsconfig.json
  tsconfig.node.json
  vite.config.ts
docker-compose.yml
README.md
```

## Task 1: Backend Project Skeleton

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/errors.py`
- Create: `backend/app/__init__.py`
- Create package marker files listed in the target structure.
- Test: `backend/tests/conftest.py`

- [ ] **Step 1: Create backend package and dependency config**

Create `backend/pyproject.toml`:

```toml
[project]
name = "quant-platform-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "pydantic>=2.8.0",
  "pydantic-settings>=2.4.0",
  "sqlalchemy>=2.0.30",
  "FinanceDataReader>=0.9.90",
  "pandas>=2.2.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2.0",
  "httpx>=0.27.0",
  "ruff>=0.5.0",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"
```

- [ ] **Step 2: Create FastAPI app factory**

Create `backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="Quant Strategy Platform", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 3: Add settings and domain error types**

Create `backend/app/core/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./quant_platform.db"
    default_owner_id: str = "default"
    market_data_provider: str = "finance_data_reader"

    model_config = SettingsConfigDict(env_prefix="QUANT_", env_file=".env")


settings = Settings()
```

Create `backend/app/core/errors.py`:

```python
class AppError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    pass


class ValidationAppError(AppError):
    pass


class MarketDataError(AppError):
    pass
```

- [ ] **Step 4: Add package marker files**

Create empty `__init__.py` files for every backend package listed in the target structure.

- [ ] **Step 5: Add first API test**

Create `backend/tests/conftest.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_client() -> TestClient:
    return TestClient(create_app())
```

Create `backend/tests/test_api_dashboard.py` with the first health test:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 6: Run test**

Run:

```powershell
cd backend
python -m pytest tests/test_api_dashboard.py -v
```

Expected: `1 passed`.

- [ ] **Step 7: Commit**

Run:

```powershell
git add backend
git commit -m "feat: scaffold backend app"
```

## Task 2: Database Models and Seed Data

**Files:**
- Create: `backend/app/domain/enums.py`
- Create: `backend/app/domain/models.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Create: `backend/app/db/seed.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_repositories.py`

- [ ] **Step 1: Write model smoke test**

Create `backend/tests/test_repositories.py`:

```python
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.seed import seed_default_owner
from app.domain.models import Owner


def test_seed_default_owner_is_idempotent() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        seed_default_owner(session, "default")
        seed_default_owner(session, "default")
        owners = session.scalars(select(Owner)).all()

    assert len(owners) == 1
    assert owners[0].id == "default"
```

- [ ] **Step 2: Add enums**

Create `backend/app/domain/enums.py`:

```python
from enum import StrEnum


class StrategyMode(StrEnum):
    SAFE = "safe"
    AGGRESSIVE = "aggressive"


class PositionStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class TradeSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class TradeSource(StrEnum):
    SIGNAL_EXECUTION = "signal_execution"
    MANUAL = "manual"
    CORRECTION = "correction"


class BacktestStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
```

- [ ] **Step 3: Add SQLAlchemy base and models**

Create `backend/app/db/base.py`:

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

Create `backend/app/domain/models.py` with SQLAlchemy 2 typed mappings for `Owner`, `StrategyConfig`, `MarketPrice`, `LivePortfolio`, `Position`, `Trade`, `BacktestRun`, `BacktestDailySnapshot`, and `BacktestTrade`. Use `Numeric(18, 6)` for money and price fields, `JSON` for settings snapshots, and uniqueness on `(provider, symbol, date, adjusted)` for market prices.

- [ ] **Step 4: Add database session and seed**

Create `backend/app/db/session.py`:

```python
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
```

Create `backend/app/db/seed.py`:

```python
from sqlalchemy.orm import Session

from app.domain.models import Owner


def seed_default_owner(session: Session, owner_id: str) -> None:
    owner = session.get(Owner, owner_id)
    if owner is None:
        session.add(Owner(id=owner_id, name="Default"))
        session.commit()
```

- [ ] **Step 5: Initialize tables on startup**

Modify `backend/app/main.py` to create tables and seed the default owner during startup:

```python
from app.core.config import settings
from app.db.base import Base
from app.db.seed import seed_default_owner
from app.db.session import SessionLocal, engine
```

Inside `create_app()` add:

```python
    @app.on_event("startup")
    def startup() -> None:
        Base.metadata.create_all(engine)
        with SessionLocal() as session:
            seed_default_owner(session, settings.default_owner_id)
```

- [ ] **Step 6: Run repository test**

Run:

```powershell
cd backend
python -m pytest tests/test_repositories.py -v
```

Expected: `1 passed`.

- [ ] **Step 7: Commit**

Run:

```powershell
git add backend/app backend/tests
git commit -m "feat: add database models and seed data"
```

## Task 3: Strategy Engine and Dynamic Wave

**Files:**
- Create: `backend/app/strategy_engine/base.py`
- Create: `backend/app/strategy_engine/context.py`
- Create: `backend/app/strategy_engine/dynamic_wave.py`
- Create: `backend/app/strategy_engine/registry.py`
- Test: `backend/tests/test_dynamic_wave_strategy.py`

- [ ] **Step 1: Write Dynamic Wave tests**

Create `backend/tests/test_dynamic_wave_strategy.py` with tests for safe mode, buy threshold, split limit, quantity calculation, sell by return, sell by holding period, and PCR/LCR capital updates. Use `Decimal` for expected money values:

```python
from datetime import date
from decimal import Decimal

from app.domain.enums import StrategyMode
from app.strategy_engine.context import StrategyContext, StrategyPosition
from app.strategy_engine.dynamic_wave import DynamicWaveStrategy


def make_context(**overrides) -> StrategyContext:
    data = {
        "current_date": date(2026, 1, 3),
        "previous_close": Decimal("100"),
        "current_close": Decimal("103"),
        "capital": Decimal("1000"),
        "cash": Decimal("1000"),
        "open_positions": [],
        "settings": DynamicWaveStrategy.default_settings(),
        "trading_day_index": 1,
    }
    data.update(overrides)
    return StrategyContext(**data)


def test_dynamic_wave_mode_defaults_to_safe() -> None:
    strategy = DynamicWaveStrategy()
    assert strategy.get_mode(make_context()) == StrategyMode.SAFE


def test_should_buy_when_close_is_inside_safe_threshold() -> None:
    strategy = DynamicWaveStrategy()
    signal = strategy.should_buy(make_context(current_close=Decimal("103")))
    assert signal.should_buy is True
    assert signal.reason == "aod_threshold"


def test_should_not_buy_when_split_limit_is_reached() -> None:
    strategy = DynamicWaveStrategy()
    positions = [
        StrategyPosition(date(2026, 1, 1), Decimal("100"), 1, StrategyMode.SAFE)
        for _ in range(7)
    ]
    signal = strategy.should_buy(make_context(open_positions=positions))
    assert signal.should_buy is False
    assert signal.reason == "split_limit_reached"


def test_position_size_uses_capital_not_cash() -> None:
    strategy = DynamicWaveStrategy()
    size = strategy.calculate_position_size(make_context(capital=Decimal("1000"), cash=Decimal("50")))
    assert size.amount == Decimal("142.857143")
    assert size.quantity == 1


def test_should_sell_when_profit_target_is_reached() -> None:
    strategy = DynamicWaveStrategy()
    position = StrategyPosition(date(2026, 1, 1), Decimal("100"), 1, StrategyMode.SAFE)
    signal = strategy.should_sell(make_context(current_close=Decimal("105")), position)
    assert signal.should_sell is True
    assert signal.reason == "profit_target"


def test_should_sell_when_max_holding_period_is_reached() -> None:
    strategy = DynamicWaveStrategy()
    position = StrategyPosition(date(2025, 12, 1), Decimal("100"), 1, StrategyMode.SAFE)
    signal = strategy.should_sell(make_context(current_close=Decimal("101")), position)
    assert signal.should_sell is True
    assert signal.reason == "max_holding_period"


def test_update_capital_applies_pcr_and_lcr() -> None:
    strategy = DynamicWaveStrategy()
    context = make_context(capital=Decimal("1000"))
    assert strategy.update_capital(context, Decimal("100")).capital == Decimal("1050.000000")
    assert strategy.update_capital(context, Decimal("-100")).capital == Decimal("970.000000")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_dynamic_wave_strategy.py -v
```

Expected: import failures because strategy engine files do not exist.

- [ ] **Step 3: Implement strategy DTOs and interface**

Create `backend/app/strategy_engine/context.py` with dataclasses:

```python
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from app.domain.enums import StrategyMode


@dataclass(frozen=True)
class StrategyPosition:
    buy_date: date
    buy_price: Decimal
    quantity: int
    mode: StrategyMode


@dataclass(frozen=True)
class StrategyContext:
    current_date: date
    previous_close: Decimal
    current_close: Decimal
    capital: Decimal
    cash: Decimal
    open_positions: list[StrategyPosition]
    settings: dict[str, Any]
    trading_day_index: int
```

Create `backend/app/strategy_engine/base.py` with `BuySignal`, `SellSignal`, `PositionSize`, `CapitalUpdate`, and abstract `Strategy`.

- [ ] **Step 4: Implement Dynamic Wave**

Create `backend/app/strategy_engine/dynamic_wave.py`:

```python
from datetime import date
from decimal import Decimal, ROUND_DOWN

from app.domain.enums import StrategyMode
from app.strategy_engine.base import BuySignal, CapitalUpdate, PositionSize, SellSignal, Strategy
from app.strategy_engine.context import StrategyContext, StrategyPosition


MONEY_QUANT = Decimal("0.000001")


class DynamicWaveStrategy(Strategy):
    strategy_type = "dynamic_wave"
    display_name = "Dynamic Wave Strategy"

    @staticmethod
    def default_settings() -> dict:
        return {
            "mode_rsi_symbol": "QQQ",
            "base_index": "QQQ",
            "profit_compounding_rate": 50,
            "loss_compounding_rate": 30,
            "capital_update": {"type": "trading_days", "interval": 20},
            "safe": {"split_count": 7, "max_holding_days": 20, "buy_threshold_percent": 3, "sell_threshold_percent": 5},
            "aggressive": {"split_count": 5, "max_holding_days": 10, "buy_threshold_percent": 5, "sell_threshold_percent": 7},
        }

    def get_mode(self, context: StrategyContext) -> StrategyMode:
        return StrategyMode.SAFE

    def should_buy(self, context: StrategyContext) -> BuySignal:
        mode = self.get_mode(context)
        mode_settings = context.settings[mode.value]
        split_count = int(mode_settings["split_count"])
        if len(context.open_positions) >= split_count:
            return BuySignal(False, "split_limit_reached")
        threshold = Decimal(str(mode_settings["buy_threshold_percent"])) / Decimal("100")
        limit_price = context.previous_close * (Decimal("1") + threshold)
        if context.current_close <= limit_price:
            size = self.calculate_position_size(context)
            if size.quantity <= 0:
                return BuySignal(False, "quantity_zero")
            return BuySignal(True, "aod_threshold")
        return BuySignal(False, "price_above_threshold")

    def should_sell(self, context: StrategyContext, position: StrategyPosition) -> SellSignal:
        mode_settings = context.settings[position.mode.value]
        return_pct = (context.current_close - position.buy_price) / position.buy_price * Decimal("100")
        if return_pct >= Decimal(str(mode_settings["sell_threshold_percent"])):
            return SellSignal(True, "profit_target", return_pct.quantize(MONEY_QUANT))
        holding_days = (context.current_date - position.buy_date).days
        if holding_days >= int(mode_settings["max_holding_days"]):
            return SellSignal(True, "max_holding_period", return_pct.quantize(MONEY_QUANT))
        return SellSignal(False, None, return_pct.quantize(MONEY_QUANT))

    def calculate_position_size(self, context: StrategyContext) -> PositionSize:
        mode_settings = context.settings[self.get_mode(context).value]
        split_count = Decimal(str(mode_settings["split_count"]))
        amount = (context.capital / split_count).quantize(MONEY_QUANT)
        quantity = int((amount / context.current_close).to_integral_value(rounding=ROUND_DOWN))
        return PositionSize(amount, quantity)

    def update_capital(self, context: StrategyContext, realized_pnl: Decimal) -> CapitalUpdate:
        if realized_pnl >= 0:
            rate = Decimal(str(context.settings["profit_compounding_rate"])) / Decimal("100")
            capital = context.capital + realized_pnl * rate
        else:
            rate = Decimal(str(context.settings["loss_compounding_rate"])) / Decimal("100")
            capital = context.capital + realized_pnl * rate
        return CapitalUpdate(capital.quantize(MONEY_QUANT))

    def get_settings_schema(self) -> dict:
        return {
            "type": "object",
            "fields": self.default_settings(),
        }
```

- [ ] **Step 5: Implement registry**

Create `backend/app/strategy_engine/registry.py`:

```python
from app.strategy_engine.base import Strategy
from app.strategy_engine.dynamic_wave import DynamicWaveStrategy


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, type[Strategy]] = {}

    def register(self, strategy_cls: type[Strategy]) -> None:
        self._strategies[strategy_cls.strategy_type] = strategy_cls

    def create(self, strategy_type: str) -> Strategy:
        return self._strategies[strategy_type]()

    def list(self) -> list[dict[str, str]]:
        return [
            {"type": strategy_type, "name": strategy_cls.display_name}
            for strategy_type, strategy_cls in self._strategies.items()
        ]


registry = StrategyRegistry()
registry.register(DynamicWaveStrategy)
```

- [ ] **Step 6: Run strategy tests**

Run:

```powershell
cd backend
python -m pytest tests/test_dynamic_wave_strategy.py -v
```

Expected: `7 passed`.

- [ ] **Step 7: Commit**

Run:

```powershell
git add backend/app/strategy_engine backend/tests/test_dynamic_wave_strategy.py
git commit -m "feat: add dynamic wave strategy engine"
```

## Task 4: Market Data Provider and Cache Repository

**Files:**
- Create: `backend/app/dto/market_data.py`
- Create: `backend/app/infrastructure/market_data/base.py`
- Create: `backend/app/infrastructure/market_data/finance_data_reader_provider.py`
- Create: `backend/app/infrastructure/market_data/cached_provider.py`
- Create: `backend/app/infrastructure/repositories/market_data.py`
- Create: `backend/app/services/market_data_service.py`
- Test: `backend/tests/test_repositories.py`

- [ ] **Step 1: Add cache repository tests**

Append to `backend/tests/test_repositories.py` a test that inserts two OHLCV rows and reads them back by symbol/date range.

- [ ] **Step 2: Add OHLCV DTO**

Create `backend/app/dto/market_data.py`:

```python
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class OhlcvDto(BaseModel):
    symbol: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    adjusted: bool = True
```

- [ ] **Step 3: Add provider interface and FinanceDataReader implementation**

Create `backend/app/infrastructure/market_data/base.py` with a `MarketDataProvider` protocol exposing `get_ohlcv(symbol, start_date, end_date)`.

Create `backend/app/infrastructure/market_data/finance_data_reader_provider.py` that calls `FinanceDataReader.DataReader(symbol, start, end)`, normalizes columns to `OhlcvDto`, and raises `MarketDataError("market_data_provider_failed", message)` on failures.

- [ ] **Step 4: Add cache repository**

Create `backend/app/infrastructure/repositories/market_data.py` with:

```python
class MarketPriceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_prices(self, provider: str, symbol: str, start_date: date, end_date: date) -> list[MarketPrice]:
        stmt = (
            select(MarketPrice)
            .where(MarketPrice.provider == provider)
            .where(MarketPrice.symbol == symbol)
            .where(MarketPrice.date >= start_date)
            .where(MarketPrice.date <= end_date)
            .order_by(MarketPrice.date)
        )
        return list(self.session.scalars(stmt))

    def upsert_prices(self, provider: str, prices: list[OhlcvDto]) -> None:
        for price in prices:
            existing = self.session.scalar(
                select(MarketPrice)
                .where(MarketPrice.provider == provider)
                .where(MarketPrice.symbol == price.symbol)
                .where(MarketPrice.date == price.date)
                .where(MarketPrice.adjusted == price.adjusted)
            )
            if existing is None:
                self.session.add(MarketPrice(provider=provider, **price.model_dump()))
            else:
                for key, value in price.model_dump().items():
                    setattr(existing, key, value)
        self.session.commit()
```

- [ ] **Step 5: Add cached service**

Create `backend/app/services/market_data_service.py` that checks cache first, fetches missing ranges from the provider, upserts, and returns date-sorted `OhlcvDto` rows.

- [ ] **Step 6: Run tests**

Run:

```powershell
cd backend
python -m pytest tests/test_repositories.py -v
```

Expected: repository tests pass without external network.

- [ ] **Step 7: Commit**

Run:

```powershell
git add backend/app/dto/market_data.py backend/app/infrastructure backend/app/services/market_data_service.py backend/tests/test_repositories.py
git commit -m "feat: add cached market data provider"
```

## Task 5: Backtest Engine

**Files:**
- Create: `backend/app/backtest_engine/simulator.py`
- Create: `backend/app/backtest_engine/metrics.py`
- Create: `backend/app/backtest_engine/engine.py`
- Test: `backend/tests/fixtures.py`
- Test: `backend/tests/test_backtest_engine.py`

- [ ] **Step 1: Add fixed OHLCV fixture**

Create `backend/tests/fixtures.py` with deterministic daily close data that triggers at least one buy and one sell:

```python
from datetime import date
from decimal import Decimal

from app.dto.market_data import OhlcvDto


def simple_prices() -> list[OhlcvDto]:
    closes = ["100", "103", "108", "107", "106", "112"]
    return [
        OhlcvDto(
            symbol="TEST",
            date=date(2026, 1, index + 1),
            open=Decimal(close),
            high=Decimal(close),
            low=Decimal(close),
            close=Decimal(close),
            volume=1000,
        )
        for index, close in enumerate(closes)
    ]
```

- [ ] **Step 2: Write engine test**

Create `backend/tests/test_backtest_engine.py`:

```python
from decimal import Decimal

from app.backtest_engine.engine import BacktestEngine
from app.strategy_engine.dynamic_wave import DynamicWaveStrategy
from tests.fixtures import simple_prices


def test_backtest_engine_generates_snapshots_and_trades() -> None:
    engine = BacktestEngine()
    result = engine.run(
        strategy=DynamicWaveStrategy(),
        prices=simple_prices(),
        initial_capital=Decimal("1000"),
        fee_rate=Decimal("0.1"),
        slippage_rate=Decimal("0"),
        settings=DynamicWaveStrategy.default_settings(),
    )

    assert len(result.daily_snapshots) == 6
    assert len(result.trades) >= 2
    assert result.summary.total_trades == len(result.trades)
    assert result.summary.final_asset > Decimal("0")
    assert result.summary.cumulative_fees > Decimal("0")
```

- [ ] **Step 3: Implement simulator and result dataclasses**

Create `backend/app/backtest_engine/simulator.py` with dataclasses `SimulatedTrade`, `DailySnapshot`, and `BacktestResult`.

- [ ] **Step 4: Implement metrics**

Create `backend/app/backtest_engine/metrics.py` with functions for total return, CAGR, MDD, win rate, total trades, average holding days, and cumulative fees. Use Decimal arithmetic for money outputs.

- [ ] **Step 5: Implement engine**

Create `backend/app/backtest_engine/engine.py` with a daily loop that builds `StrategyContext`, sells existing positions, buys one new position when allowed, applies buy/sell fees, tracks cash/capital separately, records daily snapshots, and returns metrics.

- [ ] **Step 6: Run engine tests**

Run:

```powershell
cd backend
python -m pytest tests/test_backtest_engine.py -v
```

Expected: `1 passed`.

- [ ] **Step 7: Commit**

Run:

```powershell
git add backend/app/backtest_engine backend/tests/fixtures.py backend/tests/test_backtest_engine.py
git commit -m "feat: add backtest engine"
```

## Task 6: Repositories and Application Services

**Files:**
- Create: `backend/app/infrastructure/repositories/strategies.py`
- Create: `backend/app/infrastructure/repositories/portfolios.py`
- Create: `backend/app/infrastructure/repositories/trades.py`
- Create: `backend/app/infrastructure/repositories/backtests.py`
- Create: `backend/app/services/strategy_config_service.py`
- Create: `backend/app/services/dashboard_service.py`
- Create: `backend/app/services/signal_execution_service.py`
- Create: `backend/app/services/backtest_service.py`
- Test: `backend/tests/test_repositories.py`

- [ ] **Step 1: Add service-level repository tests**

Extend `backend/tests/test_repositories.py` to create a strategy config, live portfolio, open position, and trade, then assert each repository can read records by `strategy_config_id`.

- [ ] **Step 2: Implement repositories**

Each repository should accept a `Session` in `__init__` and expose explicit methods with concrete signatures:

```python
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.domain.models import BacktestRun, LivePortfolio, Position, StrategyConfig, Trade


class StrategyConfigRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        owner_id: str,
        name: str,
        strategy_type: str,
        symbol: str,
        initial_capital: Decimal,
        fee_rate: Decimal,
        slippage_rate: Decimal,
        settings_json: dict[str, Any],
    ) -> StrategyConfig:
        raise NotImplementedError

    def get(self, config_id: int) -> StrategyConfig | None:
        raise NotImplementedError

    def list_by_owner(self, owner_id: str) -> list[StrategyConfig]:
        raise NotImplementedError


class PortfolioRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_for_config(self, strategy_config_id: int, initial_capital: Decimal) -> LivePortfolio:
        raise NotImplementedError

    def get_by_config(self, strategy_config_id: int) -> LivePortfolio | None:
        raise NotImplementedError

    def save(self, portfolio: LivePortfolio) -> LivePortfolio:
        raise NotImplementedError


class PositionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_open(self, strategy_config_id: int) -> list[Position]:
        raise NotImplementedError

    def create_open(
        self,
        strategy_config_id: int,
        buy_date: date,
        buy_price: Decimal,
        quantity: int,
        mode: str,
    ) -> Position:
        raise NotImplementedError

    def close(self, position: Position, closed_at: date) -> Position:
        raise NotImplementedError


class TradeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, trade: Trade) -> Trade:
        raise NotImplementedError

    def list_by_strategy_config(self, strategy_config_id: int) -> list[Trade]:
        raise NotImplementedError


class BacktestRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_run(self, run: BacktestRun) -> BacktestRun:
        raise NotImplementedError

    def get_run(self, run_id: int) -> BacktestRun | None:
        raise NotImplementedError
```

When implementing this step, replace the `raise NotImplementedError` bodies with SQLAlchemy queries and `session.add()` / `session.commit()` calls.

Do not expose raw SQLAlchemy queries to services.

- [ ] **Step 3: Implement strategy config service**

Create `StrategyConfigService` with methods:

- `list_configs(owner_id)`
- `create_config(owner_id, request)`
- `get_config(config_id)`
- `update_config(config_id, request)`

On create, also create a `LivePortfolio` with `capital` and `cash` equal to `initial_capital`.

- [ ] **Step 4: Implement dashboard service**

Create `DashboardService.get_dashboard(config_id)` that loads config, live portfolio, open positions, latest cached prices, creates the strategy context, computes buy/sell signals, and returns a dashboard DTO.

- [ ] **Step 5: Implement signal execution service**

Create `SignalExecutionService.execute_signal(config_id, request)` that supports editable buy/sell fills, updates cash, positions, trades, fees, and realized PnL.

- [ ] **Step 6: Implement backtest service**

Create `BacktestService.run_backtest(request)` that loads config, fetches market data, runs the engine, persists a `BacktestRun`, daily snapshots, and backtest trades.

- [ ] **Step 7: Run repository and engine tests**

Run:

```powershell
cd backend
python -m pytest tests/test_repositories.py tests/test_backtest_engine.py -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

Run:

```powershell
git add backend/app/infrastructure/repositories backend/app/services backend/tests/test_repositories.py
git commit -m "feat: add repositories and application services"
```

## Task 7: REST API and CSV Downloads

**Files:**
- Create: `backend/app/dto/strategies.py`
- Create: `backend/app/dto/dashboard.py`
- Create: `backend/app/dto/trades.py`
- Create: `backend/app/dto/backtests.py`
- Create: `backend/app/api/routes_strategies.py`
- Create: `backend/app/api/routes_dashboard.py`
- Create: `backend/app/api/routes_trades.py`
- Create: `backend/app/api/routes_backtests.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_dashboard.py`
- Test: `backend/tests/test_api_backtests.py`

- [ ] **Step 1: Write API tests**

Add tests that:

- `GET /api/strategies` includes `dynamic_wave`.
- `GET /api/strategies/dynamic_wave/schema` returns settings fields.
- `POST /api/strategy-configs` creates a config.
- `GET /api/dashboard/{config_id}` returns metric fields.
- `POST /api/backtests` returns a completed run when a mocked market data service provides fixture prices.

- [ ] **Step 2: Create DTOs**

Use Pydantic models with `ConfigDict(from_attributes=True)` for database-backed responses. Keep request DTOs separate from response DTOs.

- [ ] **Step 3: Create API routers**

Each route module defines one concrete router prefix, depends on `get_session`, instantiates repositories/services, and returns DTOs:

```python
strategies_router = APIRouter(prefix="/api", tags=["strategies"])
dashboard_router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
trades_router = APIRouter(prefix="/api", tags=["trades"])
backtests_router = APIRouter(prefix="/api/backtests", tags=["backtests"])
```

- [ ] **Step 4: Register routers**

Modify `backend/app/main.py` to include all routers:

```python
from app.api.routes_backtests import router as backtests_router
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_strategies import router as strategies_router
from app.api.routes_trades import router as trades_router

app.include_router(strategies_router)
app.include_router(dashboard_router)
app.include_router(trades_router)
app.include_router(backtests_router)
```

- [ ] **Step 5: Add CSV responses**

Implement CSV endpoints with `StreamingResponse` and `text/csv` media type. Include headers:

```python
headers={"Content-Disposition": "attachment; filename=backtest-daily.csv"}
```

- [ ] **Step 6: Run API tests**

Run:

```powershell
cd backend
python -m pytest tests/test_api_dashboard.py tests/test_api_backtests.py -v
```

Expected: API tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add backend/app/api backend/app/dto backend/app/main.py backend/tests/test_api_dashboard.py backend/tests/test_api_backtests.py
git commit -m "feat: expose quant platform api"
```

## Task 8: Frontend Skeleton and Typed API Client

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/types/api.ts`
- Create: `frontend/src/api/client.ts`
- Create API modules under `frontend/src/api/`
- Create: `frontend/src/styles.css`

- [ ] **Step 1: Create Vite React TypeScript config**

Create `frontend/package.json`:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "vite": "^5.4.0",
    "typescript": "^5.5.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "lightweight-charts": "^4.2.0",
    "lucide-react": "^0.468.0"
  },
  "devDependencies": {}
}
```

- [ ] **Step 2: Add TypeScript API types**

Create `frontend/src/types/api.ts` with `StrategyInfo`, `StrategyConfig`, `DashboardResponse`, `PositionRow`, `TradeRow`, `BacktestRun`, `BacktestDailySnapshot`, and `BacktestTrade` matching backend DTO names.

- [ ] **Step 3: Add fetch client**

Create `frontend/src/api/client.ts`:

```ts
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}
```

- [ ] **Step 4: Add base app shell**

Create `App.tsx` with tab navigation for Dashboard, Backtest, Strategies, and Trades. Keep navigation state local.

- [ ] **Step 5: Add styling**

Create `styles.css` with a restrained operational tool layout: dense metric strips, compact tables, 8px max border radius, clear focus styles, and responsive two-column layout collapsing to one column.

- [ ] **Step 6: Build frontend**

Run:

```powershell
cd frontend
npm install
npm run build
```

Expected: TypeScript and Vite build succeed.

- [ ] **Step 7: Commit**

Run:

```powershell
git add frontend
git commit -m "feat: scaffold frontend app"
```

## Task 9: Frontend Screens

**Files:**
- Create components under `frontend/src/components/`
- Create pages under `frontend/src/pages/`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Build reusable components**

Create:

- `MetricStrip.tsx` for dashboard/backtest metric grids.
- `Table.tsx` for typed compact tables.
- `SignalPanel.tsx` for buy/sell signal display and execution controls.
- `SettingsForm.tsx` for schema-driven forms.
- `BacktestChart.tsx` for Lightweight Charts rendering.

- [ ] **Step 2: Implement DashboardPage**

Fetch strategy configs, choose the first config, fetch dashboard data, show metric strip, signal panels, positions, and recent trades. Add execute buttons that open editable inputs before calling signal execution.

- [ ] **Step 3: Implement BacktestPage**

Render config selector, start/end date inputs, run button, summary metrics, chart, trades table, and CSV links using backend endpoints.

- [ ] **Step 4: Implement SettingsPage**

Fetch strategies and schema, render common settings plus strategy-specific schema fields, submit to `POST /api/strategy-configs`.

- [ ] **Step 5: Implement TradesPage**

Fetch positions and trades for selected config, display tables, and add manual trade correction form.

- [ ] **Step 6: Build frontend**

Run:

```powershell
cd frontend
npm run build
```

Expected: build succeeds with no TypeScript errors.

- [ ] **Step 7: Commit**

Run:

```powershell
git add frontend/src
git commit -m "feat: add quant platform frontend screens"
```

## Task 10: Docker, README, and End-to-End Verification

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `docker-compose.yml`
- Create: `README.md`
- Modify: `.gitignore`

- [ ] **Step 1: Add backend Dockerfile**

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir ".[dev]"
COPY app ./app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Add frontend Dockerfile**

Create `frontend/Dockerfile`:

```dockerfile
FROM node:22-slim
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

- [ ] **Step 3: Add compose file**

Create `docker-compose.yml`:

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      QUANT_DATABASE_URL: sqlite:////data/quant_platform.db
    volumes:
      - quant-data:/data

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    environment:
      VITE_API_BASE_URL: http://localhost:8000
    depends_on:
      - backend

volumes:
  quant-data:
```

- [ ] **Step 4: Update gitignore**

Ensure `.gitignore` includes:

```text
.superpowers/
.venv/
__pycache__/
.pytest_cache/
quant_platform.db
node_modules/
dist/
```

- [ ] **Step 5: Write README**

Create `README.md` with:

- project overview
- backend local setup commands
- frontend local setup commands
- Docker Compose commands
- default owner behavior
- sample Dynamic Wave workflow
- test commands
- note that automatic trading is not implemented

- [ ] **Step 6: Run verification**

Run:

```powershell
cd backend
python -m pytest -v
cd ..\frontend
npm run build
cd ..
docker compose config
```

Expected:

- pytest passes
- frontend build succeeds
- compose config is valid

- [ ] **Step 7: Commit**

Run:

```powershell
git add .gitignore README.md docker-compose.yml backend/Dockerfile frontend/Dockerfile
git commit -m "chore: add docker and documentation"
```

## Final Verification

- [ ] Run backend tests:

```powershell
cd backend
python -m pytest -v
```

Expected: all backend tests pass.

- [ ] Run frontend build:

```powershell
cd frontend
npm run build
```

Expected: build succeeds.

- [ ] Start local services:

```powershell
cd backend
uvicorn app.main:app --reload
```

In a second terminal:

```powershell
cd frontend
npm run dev
```

Expected:

- Backend health: `http://localhost:8000/api/health` returns `{"status":"ok"}`.
- Frontend: `http://localhost:5173` loads the dashboard.
- A Dynamic Wave config can be created.
- Dashboard can render signals.
- Backtest can run against cached or mocked market data.
- CSV endpoints return downloadable CSV content.

## Coverage Checklist

- FastAPI backend: Task 1 and Task 7.
- React TypeScript frontend: Task 8 and Task 9.
- SQLite and repository pattern: Task 2, Task 4, Task 6.
- Service layer: Task 6.
- DTO separation: Task 4 and Task 7.
- Domain layer: Task 2.
- Strategy engine: Task 3.
- Backtest engine: Task 5.
- Strategy plugin registry: Task 3.
- Dynamic Wave settings and rules: Task 3.
- FinanceDataReader provider and cache: Task 4.
- Live signal execution and manual correction: Task 6, Task 7, Task 9.
- Backtest metrics and CSV downloads: Task 5 and Task 7.
- Lightweight Charts: Task 9.
- Docker and README: Task 10.
