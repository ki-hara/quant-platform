from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.seed import seed_default_owner
from app.db.session import create_engine_kwargs, engine as application_engine
from app.dto.market_data import OhlcvDto
from app.domain.enums import StrategyMode, TradeSide, TradeSource
from app.domain.models import Owner
from app.infrastructure.repositories.portfolios import PortfolioRepository, PositionRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.infrastructure.repositories.trades import TradeRepository
from app.infrastructure.repositories.market_data import MarketPriceRepository


def test_create_engine_kwargs_adds_sqlite_thread_check_override() -> None:
    assert create_engine_kwargs("sqlite:///./quant_platform.db") == {
        "connect_args": {"check_same_thread": False}
    }


def test_create_engine_kwargs_omits_sqlite_args_for_postgresql() -> None:
    assert create_engine_kwargs("postgresql+psycopg://user:pass@example.com/app") == {}


def test_application_sqlite_engine_enables_foreign_key_checks() -> None:
    with application_engine.connect() as connection:
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1


def test_seed_default_owner_is_idempotent() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        seed_default_owner(session, "default")
        seed_default_owner(session, "default")
        owners = session.scalars(select(Owner)).all()

    owners_by_id = {owner.id: owner for owner in owners}
    assert set(owners_by_id) == {"default", "guest"}
    assert owners_by_id["default"].is_admin is True
    assert owners_by_id["guest"].is_admin is False
    assert owners_by_id["guest"].is_active is True


def test_market_price_repository_upserts_and_lists_prices_by_symbol_and_range() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = MarketPriceRepository(session)
        repository.upsert_prices(
            "test-provider",
            [
                OhlcvDto(
                    symbol="005930",
                    date=date(2024, 1, 3),
                    open=Decimal("100"),
                    high=Decimal("110"),
                    low=Decimal("95"),
                    close=Decimal("105"),
                    volume=1000,
                ),
                OhlcvDto(
                    symbol="005930",
                    date=date(2024, 1, 2),
                    open=Decimal("90"),
                    high=Decimal("108"),
                    low=Decimal("89"),
                    close=Decimal("100"),
                    volume=900,
                ),
            ],
        )

        prices = repository.list_prices(
            "test-provider",
            "005930",
            date(2024, 1, 2),
            date(2024, 1, 3),
        )

    assert [price.date for price in prices] == [date(2024, 1, 2), date(2024, 1, 3)]
    assert [price.symbol for price in prices] == ["005930", "005930"]
    assert [price.close for price in prices] == [Decimal("100.000000"), Decimal("105.000000")]
    assert [int(price.volume) for price in prices] == [900, 1000]


def test_repositories_read_live_records_by_strategy_config_id() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        seed_default_owner(session, "default")
        configs = StrategyConfigRepository(session)
        portfolios = PortfolioRepository(session)
        positions = PositionRepository(session)
        trades = TradeRepository(session)

        config = configs.create(
            owner_id="default",
            name="Live Strategy",
            strategy_type="dynamic_wave",
            symbol="005930",
            initial_capital=Decimal("1000000"),
            fee_rate=Decimal("0.1"),
            slippage_rate=Decimal("0.0"),
            settings_json={"safe": {"split_count": 7}},
        )
        portfolio = portfolios.create_for_config(config)
        position = positions.create_open(
            strategy_config_id=config.id,
            buy_date=date(2026, 1, 2),
            buy_price=Decimal("50000"),
            quantity=Decimal("3"),
            mode=StrategyMode.SAFE,
        )
        trade = trades.create(
            strategy_config_id=config.id,
            trade_date=date(2026, 1, 2),
            side=TradeSide.BUY,
            quantity=Decimal("3"),
            price=Decimal("50000"),
            fee=Decimal("150"),
            realized_pnl=Decimal("0"),
            sell_reason=None,
            source=TradeSource.SIGNAL_EXECUTION,
        )

        assert configs.get(config.id) == config
        assert configs.list_by_owner("default") == [config]
        assert portfolios.get_by_config(config.id) == portfolio
        assert positions.list_open(config.id) == [position]
        assert positions.list_by_strategy_config(config.id) == [position]
        assert trades.list_by_strategy_config(config.id) == [trade]
