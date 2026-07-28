from datetime import date
from decimal import Decimal

import pytest

from app.backtest_engine.engine import BacktestEngine
from app.domain.enums import BacktestModePolicy, BacktestPositionSizingPolicy, StrategyMode
from app.dto.market_data import OhlcvDto
from app.strategy_engine.base import BuySignal, CapitalUpdate, PositionSize, SellSignal, Strategy
from app.strategy_engine.context import StrategyContext, StrategyPosition
from app.strategy_engine.dynamic_wave import DynamicWaveStrategy
from app.strategy_engine.radar0458_pro import Radar0458ProStrategy
from tests.fixtures import simple_prices


def assert_money(actual: Decimal, expected: str) -> None:
    assert actual == Decimal(expected)


class _ScheduledReplacementStrategy(Strategy):
    strategy_type = "scheduled_replacement"
    display_name = "Scheduled Replacement Strategy"

    def __init__(self, sell_date: date, sell_buy_date: date) -> None:
        self.sell_date = sell_date
        self.sell_buy_date = sell_buy_date

    def get_mode(self, context: StrategyContext) -> StrategyMode:
        return context.effective_mode

    def should_buy(self, context: StrategyContext) -> BuySignal:
        return BuySignal(context.current_date <= self.sell_buy_date, "scheduled_buy")

    def should_sell(self, context: StrategyContext, position: StrategyPosition) -> SellSignal:
        should_sell = context.current_date == self.sell_date and position.buy_date == date(
            2026, 1, 2
        )
        return SellSignal(should_sell, "scheduled_sell" if should_sell else None)

    def calculate_position_size(self, context: StrategyContext) -> PositionSize:
        return PositionSize(amount=Decimal("1"), quantity=1)

    def update_capital(self, context: StrategyContext, realized_pnl: Decimal) -> CapitalUpdate:
        return CapitalUpdate(context.capital)

    def get_settings_schema(self) -> dict:
        return {"type": "object", "fields": {}}


def test_full_ladder_sell_does_not_fund_same_day_replacement_buy() -> None:
    prices = [_price(date(2026, 1, day), "10") for day in range(1, 11)]
    result = BacktestEngine().run(
        strategy=_ScheduledReplacementStrategy(
            sell_date=date(2026, 1, 9),
            sell_buy_date=date(2026, 1, 10),
        ),
        prices=prices,
        initial_capital=Decimal("100"),
        fee_rate=Decimal("0"),
        slippage_rate=Decimal("0"),
        settings={
            "safe": {"split_count": 7},
            "capital_update": {"type": "trading_days", "interval": 0},
        },
    )

    trades_on_sell_date = [trade for trade in result.trades if trade.date == date(2026, 1, 9)]
    trades_on_next_date = [trade for trade in result.trades if trade.date == date(2026, 1, 10)]

    assert [trade.side for trade in trades_on_sell_date] == ["SELL"]
    assert trades_on_sell_date[0].open_position_count == 6
    assert [trade.side for trade in trades_on_next_date] == ["BUY"]
    assert trades_on_next_date[0].open_position_count == 7


def test_below_limit_start_preserves_same_day_sell_then_buy_behavior() -> None:
    prices = [_price(date(2026, 1, day), "10") for day in range(1, 9)]
    result = BacktestEngine().run(
        strategy=_ScheduledReplacementStrategy(
            sell_date=date(2026, 1, 8),
            sell_buy_date=date(2026, 1, 8),
        ),
        prices=prices,
        initial_capital=Decimal("100"),
        fee_rate=Decimal("0"),
        slippage_rate=Decimal("0"),
        settings={
            "safe": {"split_count": 7},
            "capital_update": {"type": "trading_days", "interval": 0},
        },
    )

    trades_on_sell_date = [trade for trade in result.trades if trade.date == date(2026, 1, 8)]

    assert [trade.side for trade in trades_on_sell_date] == ["SELL", "BUY"]
    assert [trade.open_position_count for trade in trades_on_sell_date] == [5, 6]


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
    assert [trade.open_position_count for trade in result.trades] == [1, 0, 1, 2, 1, 0]
    assert [trade.cash_after for trade in result.trades] == [
        Decimal("896.897000"),
        Decimal("1004.789000"),
        Decimal("897.682000"),
        Decimal("791.576000"),
        Decimal("903.464000"),
        Decimal("1015.352000"),
    ]
    assert [trade.capital_after for trade in result.trades] == [
        Decimal("1000.000000"),
        Decimal("1000.000000"),
        Decimal("1000.000000"),
        Decimal("1000.000000"),
        Decimal("1000.000000"),
        Decimal("1000.000000"),
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

    assert (
        BacktestEngine()._is_capital_update_due(
            settings,
            1,
            prices,
            date(2027, 1, 4),
        )
        is True
    )


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


def test_position_sizing_policy_controls_buy_quantity_basis() -> None:
    settings = DynamicWaveStrategy.default_settings()
    settings["safe"] = {
        **settings["safe"],
        "buy_threshold_percent": 0,
        "sell_threshold_percent": 99,
    }
    prices = [
        _price(date(2026, 1, 1), "30"),
        _price(date(2026, 1, 2), "25"),
    ]

    fixed_quantity = BacktestEngine().run(
        strategy=DynamicWaveStrategy(),
        prices=prices,
        initial_capital=Decimal("700"),
        fee_rate=Decimal("0"),
        slippage_rate=Decimal("0"),
        settings=settings,
        position_sizing_policy=BacktestPositionSizingPolicy.FIXED_QUANTITY,
    )
    full_allocation = BacktestEngine().run(
        strategy=DynamicWaveStrategy(),
        prices=prices,
        initial_capital=Decimal("700"),
        fee_rate=Decimal("0"),
        slippage_rate=Decimal("0"),
        settings=settings,
        position_sizing_policy=BacktestPositionSizingPolicy.FULL_ALLOCATION,
    )

    assert fixed_quantity.trades[0].quantity == 3
    assert full_allocation.trades[0].quantity == 4


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


def test_start_of_day_split_limit_uses_effective_mode_configuration() -> None:
    settings = {
        "safe": {"split_count": 7},
        "aggressive": {"split_count": 5},
    }
    engine = BacktestEngine()

    assert (
        engine._is_start_of_day_split_limit_reached(
            settings,
            StrategyMode.SAFE,
            starting_open_position_count=6,
        )
        is False
    )
    assert (
        engine._is_start_of_day_split_limit_reached(
            settings,
            StrategyMode.SAFE,
            starting_open_position_count=7,
        )
        is True
    )
    assert (
        engine._is_start_of_day_split_limit_reached(
            settings,
            StrategyMode.AGGRESSIVE,
            starting_open_position_count=5,
        )
        is True
    )


def test_weekly_rsi_mode_transition_uses_current_mode_split_count_for_buy_gate() -> None:
    prices = [
        _price(date(2026, 6, 15), "10"),
        _price(date(2026, 6, 16), "10"),
        _price(date(2026, 6, 17), "10"),
        _price(date(2026, 6, 18), "10"),
        _price(date(2026, 6, 19), "10"),
        _price(date(2026, 6, 22), "10"),
    ]
    rsi_prices = _weekly_prices(
        [
            "100",
            "99",
            "100",
            "99",
            "100",
            "99",
            "100",
            "99",
            "100",
            "99",
            "100",
            "99",
            "100",
            "99",
            "100",
            "100",
        ],
        first_week_ending=date(2026, 3, 6),
    )

    result = BacktestEngine().run(
        strategy=_ScheduledReplacementStrategy(
            sell_date=date(2026, 7, 1),
            sell_buy_date=date(2026, 6, 22),
        ),
        prices=prices,
        initial_capital=Decimal("100"),
        fee_rate=Decimal("0"),
        slippage_rate=Decimal("0"),
        settings={
            "safe": {"split_count": 7},
            "aggressive": {"split_count": 4},
            "capital_update": {"type": "trading_days", "interval": 0},
        },
        mode_policy=BacktestModePolicy.WEEKLY_RSI,
        rsi_prices=rsi_prices,
    )

    assert [trade.date for trade in result.trades if trade.side == "BUY"] == [
        date(2026, 6, 16),
        date(2026, 6, 17),
        date(2026, 6, 18),
        date(2026, 6, 19),
    ]
    transition_snapshot = next(
        snapshot for snapshot in result.daily_snapshots if snapshot.date == date(2026, 6, 22)
    )
    assert transition_snapshot.mode == StrategyMode.AGGRESSIVE
    assert transition_snapshot.mode_rule_code == "A1"


@pytest.mark.parametrize(
    "split_count",
    [None, "", "invalid", Decimal("Infinity"), float("inf")],
)
def test_start_of_day_split_limit_is_disabled_for_unusable_values(split_count: object) -> None:
    assert (
        BacktestEngine()._is_start_of_day_split_limit_reached(
            {"safe": {"split_count": split_count}},
            StrategyMode.SAFE,
            starting_open_position_count=7,
        )
        is False
    )


def test_start_of_day_split_limit_is_disabled_without_a_positive_limit() -> None:
    engine = BacktestEngine()

    assert (
        engine._is_start_of_day_split_limit_reached(
            {},
            StrategyMode.SAFE,
            starting_open_position_count=7,
        )
        is False
    )
    assert (
        engine._is_start_of_day_split_limit_reached(
            {"safe": {"split_count": 0}},
            StrategyMode.SAFE,
            starting_open_position_count=7,
        )
        is False
    )


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


def _run_radar(closes: list[str], settings: dict | None = None):
    return BacktestEngine().run(
        strategy=Radar0458ProStrategy(),
        prices=[_price(date(2026, 1, i + 1), close) for i, close in enumerate(closes)],
        initial_capital=Decimal("10000"),
        fee_rate=Decimal("0"),
        slippage_rate=Decimal("0"),
        settings=settings or {"pro_profile": "pro1"},
    )


def test_radar_refills_the_lowest_empty_regular_tier_on_a_later_day() -> None:
    result = _run_radar(["100", "90", "80", "70", "85", "84"])
    buys = [trade for trade in result.trades if trade.side == "BUY"]
    assert [trade.radar_tier for trade in buys] == [1, 2, 3, 2]


def test_radar_start_of_day_occupancy_delays_same_day_tier_refill() -> None:
    result = _run_radar(["100", "90"] + ["89"] * 10 + ["88"])
    day_twelve = [trade for trade in result.trades if trade.date == date(2026, 1, 12)]
    day_thirteen_buys = [
        trade for trade in result.trades if trade.date == date(2026, 1, 13) and trade.side == "BUY"
    ]
    assert [trade.side for trade in day_twelve] == ["SELL"]
    assert [trade.radar_tier for trade in day_thirteen_buys] == [1]


def test_radar_run_uses_profile_and_cycle_capital_from_settings_snapshot() -> None:
    settings = {"pro_profile": "pro1"}
    result = _run_radar(["100", "90", "80", "70"], settings)
    buys = [trade for trade in result.trades if trade.side == "BUY"]
    assert [trade.radar_profile for trade in buys] == ["pro1", "pro1", "pro1"]
    assert [trade.radar_cycle_capital for trade in buys] == [Decimal("10000")] * 3


def test_radar_uses_reserve_tier_seven_only_after_regular_tiers_are_occupied() -> None:
    result = _run_radar(["100", "90", "80", "70", "60", "50", "40", "30"])
    buys = [trade for trade in result.trades if trade.side == "BUY"]
    assert [trade.radar_tier for trade in buys] == [1, 2, 3, 4, 5, 6, 7]
    assert buys[-1].quantity == 42


def test_radar_applies_one_hundred_percent_realized_pnl_to_capital() -> None:
    result = _run_radar(["100", "90", "91"])
    sell = next(trade for trade in result.trades if trade.side == "SELL")
    assert sell.realized_pnl == Decimal("5.000000")
    assert sell.capital_after == Decimal("10005.000000")
    assert result.daily_snapshots[-1].capital == Decimal("10005.000000")
