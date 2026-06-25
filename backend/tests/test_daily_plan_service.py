from collections.abc import Generator
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.seed import seed_default_owner
from app.domain.enums import ModeConfirmationSource, StrategyMode, TradeSide, TradeSource
from app.dto.market_data import OhlcvDto
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.infrastructure.repositories.modes import ModeStateRepository
from app.infrastructure.repositories.portfolios import PortfolioRepository, PositionRepository
from app.infrastructure.repositories.trades import TradeRepository
from app.services.daily_plan_service import DailyPlanService
from app.services.mode_service import ModeService
from app.services.strategy_config_service import StrategyConfigCreateRequest, StrategyConfigService
from app.strategy_engine.dynamic_wave import DynamicWaveStrategy


def create_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    seed_default_owner(session, "default")
    return session


def create_config(session: Session):
    settings = DynamicWaveStrategy.default_settings()
    settings["fee_rate_percent"] = "0.1"
    return StrategyConfigService(session).create_config(
        "default",
        StrategyConfigCreateRequest(
            name="Live Strategy",
            strategy_type="dynamic_wave",
            symbol="TEST",
            initial_capital=Decimal("1000"),
            fee_rate=Decimal("0.1"),
            slippage_rate=Decimal("0"),
            settings_json=settings,
        ),
    )


def seed_daily_prices(
    session: Session,
    symbol: str,
    start_date: date,
    closes: list[str],
) -> None:
    MarketPriceRepository(session).upsert_prices(
        "finance_data_reader",
        [
            OhlcvDto(
                symbol=symbol,
                date=start_date + timedelta(days=index),
                open=Decimal(close),
                high=Decimal(close),
                low=Decimal(close),
                close=Decimal(close),
                volume=1000 + index,
            )
            for index, close in enumerate(closes)
        ],
    )


def seed_weekly_prices(
    session: Session,
    closes: list[str],
    *,
    symbol: str = "QQQ",
    first_week_ending: date = date(2026, 2, 27),
) -> None:
    MarketPriceRepository(session).upsert_prices(
        "finance_data_reader",
        [
            OhlcvDto(
                symbol=symbol,
                date=first_week_ending + timedelta(days=7 * index),
                open=Decimal(close),
                high=Decimal(close),
                low=Decimal(close),
                close=Decimal(close),
                volume=1000,
            )
            for index, close in enumerate(closes)
        ],
    )


def test_daily_plan_uses_last_completed_close_and_confirmed_mode() -> None:
    with create_session() as session:
        config = create_config(session)
        plan_service = DailyPlanService(session)
        seed_daily_prices(
            session,
            "TEST",
            date(2026, 6, 18),
            ["99", "100", "101"],
        )
        seed_weekly_prices(
            session,
            [
                "99",
                "100",
                "101",
                "102",
                "103",
                "104",
                "105",
                "106",
                "107",
                "108",
                "109",
                "110",
                "111",
                "112",
                "113",
                "114",
                "113",
                "112",
            ],
        )
        ModeService(session).get_mode_recommendation(config.id, as_of=date(2026, 6, 19))
        ModeService(session).set_confirmed_mode(config.id, StrategyMode.SAFE)

        plan = plan_service.get_daily_plan(config.id, today=date(2026, 6, 20))

        assert plan.plan_date == date(2026, 6, 20)
        assert plan.market_data_as_of == date(2026, 6, 20)
        assert plan.confirmed_mode == StrategyMode.SAFE
        assert plan.recommended_mode == StrategyMode.SAFE
        assert plan.differs is False
        assert plan.previous_close == Decimal("101.000000")
        assert plan.LOC.limit_price == Decimal("104.030000")
        assert plan.LOC.quantity == 1
        assert plan.buy_available is True
        assert plan.LOC.blocking_reason is None


def test_daily_plan_calculates_exact_loc_price_and_quantity_from_previous_close() -> None:
    with create_session() as session:
        config = create_config(session)
        plan_service = DailyPlanService(session)
        seed_daily_prices(
            session,
            "TEST",
            date(2026, 6, 18),
            ["99", "100"],
        )
        seed_weekly_prices(
            session,
            [
                "99",
                "100",
                "101",
                "102",
                "103",
                "104",
                "105",
                "106",
                "107",
                "108",
                "109",
                "110",
                "111",
                "112",
                "113",
                "114",
                "113",
                "112",
            ],
        )
        ModeService(session).get_mode_recommendation(config.id, as_of=date(2026, 6, 19))

        plan = plan_service.get_daily_plan(config.id, today=date(2026, 6, 19))

        assert plan.market_data_as_of == date(2026, 6, 19)
        assert plan.previous_close == Decimal("100.000000")
        assert plan.LOC.limit_price == Decimal("103.000000")
        assert plan.LOC.allocation == Decimal("142.857143")
        assert plan.LOC.quantity == 1
        assert plan.LOC.required_cash == Decimal("103.103000")
        assert plan.buy_available is True
        assert plan.open_position_count == 0
        assert plan.mode_split_count == 7


@pytest.mark.parametrize(
    ("seed_closes", "cash", "open_positions", "expected_reason"),
    [
        (["99", "100"], Decimal("102"), 0, "insufficient_cash"),
        (["1000", "1000"], Decimal("1000"), 0, "quantity_zero"),
        (["99", "100"], Decimal("1000"), 7, "split_limit_reached"),
    ],
)
def test_daily_plan_reports_stable_blocking_reasons(
    seed_closes: list[str],
    cash: Decimal,
    open_positions: int,
    expected_reason: str,
) -> None:
    with create_session() as session:
        config = create_config(session)
        portfolio = PortfolioRepository(session).get_by_config(config.id)
        assert portfolio is not None
        portfolio.cash = cash
        PortfolioRepository(session).save(portfolio)
        seed_daily_prices(session, "TEST", date(2026, 6, 18), seed_closes)
        seed_weekly_prices(
            session,
            [
                "99",
                "100",
                "101",
                "102",
                "103",
                "104",
                "105",
                "106",
                "107",
                "108",
                "109",
                "110",
                "111",
                "112",
                "113",
                "114",
                "113",
                "112",
            ],
        )
        ModeService(session).get_mode_recommendation(config.id, as_of=date(2026, 6, 19))
        if open_positions:
            positions = PositionRepository(session)
            for index in range(open_positions):
                positions.create_open(
                    strategy_config_id=config.id,
                    buy_date=date(2026, 6, 1) + timedelta(days=index),
                    buy_price=Decimal("100"),
                    quantity=Decimal("1"),
                    mode=StrategyMode.SAFE,
                )

        plan = DailyPlanService(session).get_daily_plan(config.id, today=date(2026, 6, 19))

        assert plan.buy_available is False
        assert plan.LOC.blocking_reason == expected_reason


def test_daily_plan_missing_previous_close_is_unavailable() -> None:
    with create_session() as session:
        config = create_config(session)
        seed_weekly_prices(
            session,
            [
                "99",
                "100",
                "101",
                "102",
                "103",
                "104",
                "105",
                "106",
                "107",
                "108",
                "109",
                "110",
                "111",
                "112",
                "113",
                "114",
                "113",
                "112",
            ],
        )

        plan = DailyPlanService(session).get_daily_plan(config.id, today=date(2026, 6, 19))

        assert plan.buy_available is False
        assert plan.LOC.blocking_reason == "market_data_unavailable"


def test_daily_plan_reuses_confirmed_mode_and_keeps_recommendation_state() -> None:
    with create_session() as session:
        config = create_config(session)
        seed_daily_prices(session, "TEST", date(2026, 6, 18), ["99", "100"])
        seed_weekly_prices(
            session,
            [
                "99",
                "100",
                "101",
                "102",
                "103",
                "104",
                "105",
                "106",
                "107",
                "108",
                "109",
                "110",
                "111",
                "112",
                "113",
                "114",
                "113",
                "112",
            ],
        )
        service = ModeService(session)
        service.get_mode_recommendation(config.id, as_of=date(2026, 6, 19))
        service.set_confirmed_mode(config.id, StrategyMode.AGGRESSIVE)

        plan = DailyPlanService(session).get_daily_plan(config.id, today=date(2026, 6, 19))
        state = ModeStateRepository(session).get(config.id)

        assert plan.confirmed_mode == StrategyMode.AGGRESSIVE
        assert plan.confirmed_source == ModeConfirmationSource.MANUAL
        assert plan.recommended_mode == StrategyMode.SAFE
        assert state is not None
        assert state.confirmed_mode == StrategyMode.AGGRESSIVE
