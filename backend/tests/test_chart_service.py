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


@pytest.mark.parametrize("reverse", [False, True])
def test_chart_deduplicates_adjusted_and_fallback_quotes(reverse):
    with create_session() as session:
        config = create_config(session)
        rows = [
            OhlcvDto(symbol="TEST", date=date(2026, 9, day),
                     open=Decimal(value), high=Decimal(value), low=Decimal(value),
                     close=Decimal(value), volume=volume, adjusted=adjusted)
            for day, adjusted, value, volume in [
                (22, False, "151.95", 10), (22, True, "151.949997", 20),
                (23, False, "146.25", 30),
            ]
        ]
        if reverse:
            rows.reverse()
        MarketPriceRepository(session).upsert_prices("finance_data_reader", rows)
        chart = ChartService(session).get_chart(config.id, "1m", today=date(2026, 9, 23))
        assert [p.date for p in chart.candles] == [date(2026, 9, 22), date(2026, 9, 23)]
        assert chart.candles[0].close == Decimal("151.949997")
        assert chart.candles[0].volume == 20
        assert chart.candles[1].close == Decimal("146.25")


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
        assert chart.LOC.value == Decimal("276.040000")
        assert chart.LOC.as_of == date(2026, 6, 18)
        assert {marker.kind for marker in chart.trade_markers} == {"buy", "sell"}
        assert chart.rsi.guides == [
            Decimal("35"),
            Decimal("40"),
            Decimal("50"),
            Decimal("60"),
            Decimal("65"),
        ]
        assert len(chart.mode_markers) == 2
        assert chart.mode_markers[0].period_start_date == date(2026, 6, 15)
        assert chart.mode_markers[0].period_end_date == date(2026, 6, 19)
        assert chart.mode_markers[0].date == date(2026, 6, 19)
        assert chart.rsi.points


def test_chart_includes_cci_series_for_configured_trend_symbols() -> None:
    with create_session() as session:
        config = create_config(session)
        seed_prices(session, "TEST", date(2026, 1, 1), 400)
        seed_prices(session, "QQQ", date(2026, 1, 2), 240)
        seed_prices(session, "SOXL", date(2026, 1, 2), 240)

        chart = ChartService(session).get_chart(config.id, range_key="6m", today=date(2026, 8, 1))

        assert [series.symbol for series in chart.cci.series] == ["QQQ", "SOXL"]
        assert chart.cci.guides == [Decimal("0")]
        assert all(series.points for series in chart.cci.series)


def test_chart_rsi_includes_current_week_for_display() -> None:
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
            ],
        )
        MarketPriceRepository(session).upsert_prices(
            "finance_data_reader",
            [
                OhlcvDto(
                    symbol="QQQ",
                    date=date(2026, 6, 25),
                    open=Decimal("111"),
                    high=Decimal("111"),
                    low=Decimal("111"),
                    close=Decimal("111"),
                    volume=1000,
                ),
            ],
        )

        chart = ChartService(session).get_chart(config.id, range_key="6m", today=date(2026, 6, 25))

        assert chart.rsi.points
        assert max(point.date for point in chart.rsi.points) == date(2026, 6, 26)


def test_chart_shows_current_mode_period_marker_from_week_start() -> None:
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
        ModeService(session).get_mode_recommendation(config.id, as_of=date(2026, 7, 6))

        chart = ChartService(session).get_chart(config.id, range_key="6m", today=date(2026, 7, 6))

        assert len(chart.mode_markers) == 4
        assert chart.mode_markers[-1].period_start_date == date(2026, 7, 6)
        assert chart.mode_markers[-1].period_end_date == date(2026, 7, 10)
        assert chart.mode_markers[-1].date == date(2026, 7, 10)


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


def test_radar_chart_uses_profile_loc_without_dynamic_wave_indicators() -> None:
    with create_session() as session:
        config = StrategyConfigService(session).create_config(
            "default",
            StrategyConfigCreateRequest(
                name="Radar",
                strategy_type="radar0458_pro",
                symbol="SOXL",
                initial_capital=Decimal("3000"),
                fee_rate=Decimal("0"),
                slippage_rate=Decimal("0"),
                settings_json={"pro_profile": "pro2"},
            ),
        )
        seed_prices(session, "SOXL", date(2026, 7, 24), 1)

        chart = ChartService(session).get_chart(
            config.id, range_key="1m", today=date(2026, 7, 27)
        )

        assert chart.LOC.value == Decimal("99.99")
        assert chart.LOC.as_of == date(2026, 7, 24)
        assert chart.rsi.guides == []
        assert chart.rsi.points == []
        assert chart.mode_markers == []
        assert chart.cci.guides == []
        assert chart.cci.series == []


def test_chart_missing_config_raises_value_error() -> None:
    with create_session() as session:
        with pytest.raises(ValueError, match="Strategy config not found"):
            ChartService(session).get_chart(999, range_key="6m", today=date(2026, 6, 20))


def test_missing_friday_quote_does_not_create_next_week_marker() -> None:
    with create_session() as session:
        config = create_config(session)
        seed_weekly_prices(session, [str(100 + index) for index in range(17)])
        service = ChartService(session)
        before = service._mode_markers(config.id, date(2026, 6, 1), date(2026, 6, 25))
        after = service._mode_markers(config.id, date(2026, 6, 1), date(2026, 6, 27))
        assert [row.date for row in before] == [row.date for row in after]
        assert after[-1].date == date(2026, 6, 26)


def test_friday_holiday_uses_thursday_close_for_next_week_marker() -> None:
    with create_session() as session:
        config = create_config(session)
        seed_weekly_prices(session, [str(100 + index) for index in range(16)])
        seed_prices(session, "QQQ", date(2026, 6, 18), 1)
        markers = ChartService(session)._mode_markers(
            config.id, date(2026, 6, 1), date(2026, 6, 18),
        )
        assert markers[-1].period_start_date == date(2026, 6, 22)
        assert markers[-1].date == date(2026, 6, 26)


def test_chart_defaults_to_confirmed_market_date(monkeypatch) -> None:
    with create_session() as session:
        config = create_config(session)
        seed_prices(session, "TEST", date(2026, 7, 13), 3)
        from app.services import chart_service

        monkeypatch.setattr(
            chart_service,
            "latest_confirmed_market_date",
            lambda symbol, now=None: date(2026, 7, 14),
        )

        chart = ChartService(session).get_chart(config.id, range_key="1m", today=None)

    assert [candle.date for candle in chart.candles] == [date(2026, 7, 13), date(2026, 7, 14)]
