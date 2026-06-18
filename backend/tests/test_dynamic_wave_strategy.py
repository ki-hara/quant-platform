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
