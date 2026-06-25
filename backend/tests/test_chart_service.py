from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.seed import seed_default_owner
from app.domain.enums import StrategyMode, TradeSide, TradeSource
from app.dto.market_data import OhlcvDto
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.infrastructure.repositories.modes import ModeStateRepository
from app.infrastructure.repositories.portfolios import PositionRepository
from app.infrastructure.repositories.trades import TradeRepository
from app.services.chart_service import ChartService
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


def seed_prices(
    session: Session,
    symbol: str,
    start_date: date,
    count: int,
) -> None:
    MarketPriceRepository(session).upsert_prices(
        "finance_data_reader",
        [
            OhlcvDto(
                symbol=symbol,
                date=start_date + timedelta(days=index),
                open=Decimal(str(100 + index)),
                high=Decimal(str(101 + index)),
                low=Decimal(str(99 + index)),
                close=Decimal(str(100 + index)),
                volume=1000 + index,
            )
            for index in range(count)
        ][::-1],
    )


def seed_weekly_prices(session: Session, closes: list[str]) -> None:
    MarketPriceRepository(session).upsert_prices(
        "finance_data_reader",
        [
            OhlcvDto(
                symbol="QQQ",
                date=date(2026, 2, 27) + timedelta(days=7 * index),
                open=Decimal(close),
                high=Decimal(close),
                low=Decimal(close),
                close=Decimal(close),
                volume=1000,
            )
            for index, close in enumerate(closes)
        ],
    )


def seed_trade_markers(session: Session, config_id: int) -> None:
    trades = TradeRepository(session)
    trades.create(
        strategy_config_id=config_id,
        trade_date=date(2026, 5, 1),
        side=TradeSide.BUY,
        quantity=Decimal("1"),
        price=Decimal("100"),
        fee=Decimal("0"),
        realized_pnl=Decimal("0"),
        sell_reason=None,
        source=TradeSource.SIGNAL_EXECUTION,
    )
    trades.create(
        strategy_config_id=config_id,
        trade_date=date(2026, 5, 11),
        side=TradeSide.SELL,
        quantity=Decimal("1"),
        price=Decimal("110"),
        fee=Decimal("0"),
        realized_pnl=Decimal("10"),
        sell_reason="profit_target",
        source=TradeSource.SIGNAL_EXECUTION,
    )


def test_chart_returns_sorted_ohlcv_loc_trade_markers_and_rsi_guides() -> None:
    with create_session() as session:
        config = create_config(session)
        seed_prices(session, "TEST", date(2026, 1, 1), 400)
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
                "111",
            ],
        )
        seed_trade_markers(session, config.id)
        ModeService(session).get_mode_recommendation(config.id, as_of=date(2026, 6, 19))
        ModeStateRepository(session).get_or_create_safe(config.id).confirmed_mode = StrategyMode.SAFE

        chart = ChartService(session).get_chart(config.id, range_key="6m", today=date(2026, 6, 20))

        assert [candle.date for candle in chart.candles] == sorted(
            candle.date for candle in chart.candles
        )
        assert len(chart.candles) == 171
        assert chart.LOC.value == Decimal("278.100000")
        assert {marker.kind for marker in chart.trade_markers} == {"buy", "sell"}
        assert chart.rsi.guides == [
            Decimal("35"),
            Decimal("40"),
            Decimal("50"),
            Decimal("60"),
            Decimal("65"),
        ]
        assert chart.mode_markers
        assert chart.rsi.points


@pytest.mark.parametrize(
    ("range_key", "expected_days"),
    [("1m", 31), ("3m", 93), ("6m", 186), ("1y", 366)],
)
def test_chart_range_keys_map_to_expected_day_windows(range_key: str, expected_days: int) -> None:
    with create_session() as session:
        config = create_config(session)
        seed_prices(session, "TEST", date(2025, 6, 20), 500)
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
                "111",
            ],
        )

        chart = ChartService(session).get_chart(config.id, range_key=range_key, today=date(2026, 6, 20))

        assert len(chart.candles) == expected_days
        assert chart.candles[0].date == date(2026, 6, 20) - timedelta(days=expected_days - 1)


def test_chart_missing_config_raises_value_error() -> None:
    with create_session() as session:
        with pytest.raises(ValueError, match="Strategy config not found"):
            ChartService(session).get_chart(999, range_key="6m", today=date(2026, 6, 20))
