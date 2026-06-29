from datetime import date
from decimal import Decimal

from app.backtest_engine.engine import BacktestEngine
from app.domain.enums import BacktestModePolicy, StrategyMode
from app.dto.market_data import OhlcvDto
from app.strategy_engine.dynamic_wave import DynamicWaveStrategy
from tests.fixtures import simple_prices


def assert_money(actual: Decimal, expected: str) -> None:
    assert actual == Decimal(expected)


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
    assert len(result.trades) == 6
    assert result.summary.total_trades == len(result.trades)

    assert [trade.side for trade in result.trades] == ["BUY", "SELL", "BUY", "BUY", "SELL", "SELL"]
    assert [trade.date for trade in result.trades] == [
        date(2026, 1, 2),
        date(2026, 1, 3),
        date(2026, 1, 4),
        date(2026, 1, 5),
        date(2026, 1, 6),
        date(2026, 1, 6),
    ]
    assert [trade.quantity for trade in result.trades] == [1, 1, 1, 1, 1, 1]
    assert [trade.price for trade in result.trades] == [
        Decimal("103.000000"),
        Decimal("108.000000"),
        Decimal("107.000000"),
        Decimal("106.000000"),
        Decimal("112.000000"),
        Decimal("112.000000"),
    ]
    assert [trade.fee for trade in result.trades] == [
        Decimal("0.103000"),
        Decimal("0.108000"),
        Decimal("0.107000"),
        Decimal("0.106000"),
        Decimal("0.112000"),
        Decimal("0.112000"),
    ]
    assert [trade.realized_pnl for trade in result.trades] == [
        Decimal("0"),
        Decimal("4.789000"),
        Decimal("0"),
        Decimal("0"),
        Decimal("4.781000"),
        Decimal("5.782000"),
    ]
    assert [trade.sell_reason for trade in result.trades] == [
        None,
        "profit_target",
        None,
        None,
        "profit_target",
        "profit_target",
    ]

    final_snapshot = result.daily_snapshots[-1]
    assert final_snapshot.date == date(2026, 1, 6)
    assert_money(final_snapshot.total_asset, "1015.352000")
    assert_money(final_snapshot.cash, "1015.352000")
    assert_money(final_snapshot.position_value, "0.000000")
    assert_money(final_snapshot.cumulative_fees, "0.648000")

    assert_money(result.summary.final_asset, "1015.352000")
    assert_money(result.summary.total_return, "0.015352")
    assert_money(result.summary.mdd, "-0.001207")
    assert_money(result.summary.win_rate, "1.000000")
    assert_money(result.summary.average_holding_days, "1.333333")
    assert_money(result.summary.cumulative_fees, "0.648000")
    assert result.summary.cumulative_fees == final_snapshot.cumulative_fees


def test_calendar_monthly_capital_update_is_due_on_last_available_trading_day() -> None:
    prices = [
        _price(date(2026, 1, 29)),
        _price(date(2026, 1, 30)),
        _price(date(2026, 2, 2)),
    ]
    engine = BacktestEngine()
    settings = {"capital_update": {"type": "calendar", "period": "monthly"}}

    assert engine._is_capital_update_due(settings, 0, prices, None) is False
    assert engine._is_capital_update_due(settings, 1, prices, None) is True
    assert engine._is_capital_update_due(settings, 2, prices, None) is False


def test_calendar_monthly_update_uses_next_actual_price_after_holiday() -> None:
    prices = [_price(date(2026, 1, 29)), _price(date(2026, 1, 30))]
    settings = {"capital_update": {"type": "calendar", "period": "monthly"}}

    assert (
        BacktestEngine()._is_capital_update_due(
            settings,
            1,
            prices,
            date(2026, 2, 3),
        )
        is True
    )


def test_calendar_monthly_update_is_not_due_without_lookahead() -> None:
    prices = [_price(date(2026, 1, 15)), _price(date(2026, 1, 16))]
    settings = {"capital_update": {"type": "calendar", "period": "monthly"}}

    assert BacktestEngine()._is_capital_update_due(settings, 1, prices, None) is False


def test_calendar_quarterly_update_requires_lookahead_in_next_quarter() -> None:
    prices = [_price(date(2026, 3, 30)), _price(date(2026, 3, 31))]
    settings = {"capital_update": {"type": "calendar", "period": "quarterly"}}

    engine = BacktestEngine()
    assert engine._is_capital_update_due(settings, 1, prices, date(2026, 4, 2)) is True
    assert engine._is_capital_update_due(settings, 1, prices, date(2026, 3, 31)) is False


def test_calendar_yearly_update_requires_lookahead_in_next_year() -> None:
    prices = [_price(date(2026, 12, 30)), _price(date(2026, 12, 31))]
    settings = {"capital_update": {"type": "calendar", "period": "yearly"}}

    assert BacktestEngine()._is_capital_update_due(
        settings,
        1,
        prices,
        date(2027, 1, 4),
    ) is True


def test_fixed_aggressive_policy_sets_snapshot_and_position_modes() -> None:
    result = BacktestEngine().run(
        strategy=DynamicWaveStrategy(),
        prices=simple_prices(),
        initial_capital=Decimal("1000"),
        fee_rate=Decimal("0"),
        slippage_rate=Decimal("0"),
        settings=DynamicWaveStrategy.default_settings(),
        mode_policy=BacktestModePolicy.FIXED_AGGRESSIVE,
    )

    assert {snapshot.mode for snapshot in result.daily_snapshots} == {StrategyMode.AGGRESSIVE}
    assert result.daily_snapshots[0].mode_rule_code == "fixed_aggressive"
    assert all(trade.side != "BUY" or trade.price for trade in result.trades)


def test_weekly_rsi_mode_becomes_effective_next_week_without_friday_lookahead() -> None:
    prices = [
        _price(date(2026, 6, 19), "100"),
        _price(date(2026, 6, 22), "100"),
    ]
    rsi_prices = _weekly_prices(
        [
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
        ],
        first_week_ending=date(2026, 3, 6),
    )

    result = BacktestEngine().run(
        strategy=DynamicWaveStrategy(),
        prices=prices,
        initial_capital=Decimal("1000"),
        fee_rate=Decimal("0"),
        slippage_rate=Decimal("0"),
        settings=DynamicWaveStrategy.default_settings(),
        mode_policy=BacktestModePolicy.WEEKLY_RSI,
        rsi_prices=rsi_prices,
    )

    assert result.daily_snapshots[0].date == date(2026, 6, 19)
    assert result.daily_snapshots[0].mode == StrategyMode.SAFE
    assert result.daily_snapshots[0].mode_rule_code is None
    assert result.daily_snapshots[1].date == date(2026, 6, 22)
    assert result.daily_snapshots[1].mode == StrategyMode.SAFE
    assert result.daily_snapshots[1].mode_rule_code == "S1"


def test_loc_buy_fills_at_close_when_close_is_within_limit() -> None:
    prices = [
        _price(date(2026, 1, 1), "100"),
        OhlcvDto(
            symbol="TEST",
            date=date(2026, 1, 2),
            open=Decimal("120"),
            high=Decimal("130"),
            low=Decimal("90"),
            close=Decimal("103"),
            volume=Decimal("1000"),
        ),
    ]

    result = BacktestEngine().run(
        strategy=DynamicWaveStrategy(),
        prices=prices,
        initial_capital=Decimal("1000"),
        fee_rate=Decimal("0"),
        slippage_rate=Decimal("0"),
        settings=DynamicWaveStrategy.default_settings(),
    )

    buy = next(trade for trade in result.trades if trade.side == "BUY")
    assert buy.price == Decimal("103.000000")


def test_loc_buy_does_not_fill_when_only_low_touches_limit() -> None:
    prices = [
        _price(date(2026, 1, 1), "100"),
        OhlcvDto(
            symbol="TEST",
            date=date(2026, 1, 2),
            open=Decimal("120"),
            high=Decimal("130"),
            low=Decimal("90"),
            close=Decimal("106"),
            volume=Decimal("1000"),
        ),
    ]

    result = BacktestEngine().run(
        strategy=DynamicWaveStrategy(),
        prices=prices,
        initial_capital=Decimal("1000"),
        fee_rate=Decimal("0"),
        slippage_rate=Decimal("0"),
        settings=DynamicWaveStrategy.default_settings(),
    )

    assert result.trades == []


def test_max_holding_period_uses_trading_days_not_calendar_days() -> None:
    settings = DynamicWaveStrategy.default_settings()
    settings["safe"] = {
        **settings["safe"],
        "max_holding_days": 2,
        "sell_threshold_percent": 99,
    }
    prices = [
        _price(date(2026, 1, 1), "100"),
        _price(date(2026, 1, 2), "100"),
        _price(date(2026, 1, 5), "100"),
    ]

    result = BacktestEngine().run(
        strategy=DynamicWaveStrategy(),
        prices=prices,
        initial_capital=Decimal("1000"),
        fee_rate=Decimal("0"),
        slippage_rate=Decimal("0"),
        settings=settings,
    )

    assert [trade.side for trade in result.trades] == ["BUY", "BUY"]


def _price(day: date, close: str = "100") -> OhlcvDto:
    return OhlcvDto(
        symbol="TEST",
        date=day,
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        volume=Decimal("1000"),
    )


def _weekly_prices(closes: list[str], first_week_ending: date) -> list[OhlcvDto]:
    from datetime import timedelta

    return [
        OhlcvDto(
            symbol="QQQ",
            date=first_week_ending + timedelta(days=7 * index),
            open=Decimal(close),
            high=Decimal(close),
            low=Decimal(close),
            close=Decimal(close),
            volume=Decimal("1000"),
        )
        for index, close in enumerate(closes)
    ]
