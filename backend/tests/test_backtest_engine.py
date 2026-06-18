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
