from datetime import date
from decimal import Decimal

from app.backtest_engine.engine import BacktestEngine
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
    assert len(result.trades) == 5
    assert result.summary.total_trades == len(result.trades)

    assert [trade.side for trade in result.trades] == ["BUY", "BUY", "BUY", "SELL", "SELL"]
    assert [trade.date for trade in result.trades] == [
        date(2026, 1, 2),
        date(2026, 1, 4),
        date(2026, 1, 5),
        date(2026, 1, 6),
        date(2026, 1, 6),
    ]
    assert [trade.quantity for trade in result.trades] == [1, 1, 1, 1, 1]
    assert [trade.price for trade in result.trades] == [
        Decimal("103.000000"),
        Decimal("107.000000"),
        Decimal("106.000000"),
        Decimal("112.000000"),
        Decimal("112.000000"),
    ]
    assert [trade.fee for trade in result.trades] == [
        Decimal("0.103000"),
        Decimal("0.107000"),
        Decimal("0.106000"),
        Decimal("0.112000"),
        Decimal("0.112000"),
    ]
    assert [trade.realized_pnl for trade in result.trades] == [
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("8.785000"),
        Decimal("5.782000"),
    ]
    assert [trade.sell_reason for trade in result.trades] == [
        None,
        None,
        None,
        "profit_target",
        "profit_target",
    ]

    final_snapshot = result.daily_snapshots[-1]
    assert final_snapshot.date == date(2026, 1, 6)
    assert_money(final_snapshot.total_asset, "1019.460000")
    assert_money(final_snapshot.cash, "907.460000")
    assert_money(final_snapshot.position_value, "112.000000")
    assert_money(final_snapshot.cumulative_fees, "0.540000")

    assert_money(result.summary.final_asset, "1019.460000")
    assert_money(result.summary.total_return, "0.019460")
    assert_money(result.summary.mdd, "-0.003197")
    assert_money(result.summary.win_rate, "1.000000")
    assert_money(result.summary.average_holding_days, "2.500000")
    assert_money(result.summary.cumulative_fees, "0.540000")
    assert result.summary.cumulative_fees == final_snapshot.cumulative_fees
