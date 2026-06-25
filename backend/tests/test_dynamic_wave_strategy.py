from datetime import date
from decimal import Decimal

from app.domain.enums import StrategyMode
from app.strategy_engine.context import StrategyContext, StrategyPosition
from app.strategy_engine.dynamic_wave import DynamicWaveStrategy
from app.strategy_engine.registry import StrategyRegistry


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
        "effective_mode": StrategyMode.SAFE,
    }
    data.update(overrides)
    return StrategyContext(**data)


def test_dynamic_wave_mode_defaults_to_safe() -> None:
    strategy = DynamicWaveStrategy()
    assert strategy.get_mode(make_context()) == StrategyMode.SAFE


def test_dynamic_wave_mode_uses_context_effective_mode() -> None:
    strategy = DynamicWaveStrategy()
    assert strategy.get_mode(make_context(effective_mode=StrategyMode.AGGRESSIVE)) == StrategyMode.AGGRESSIVE


def test_default_settings_keep_rsi_symbol_and_omit_unused_base_index() -> None:
    settings = DynamicWaveStrategy.default_settings()

    assert settings["mode_rsi_symbol"] == "QQQ"
    assert "base_index" not in settings


def test_should_buy_when_close_is_inside_safe_threshold() -> None:
    strategy = DynamicWaveStrategy()
    signal = strategy.should_buy(make_context(current_close=Decimal("103")))
    assert signal.should_buy is True
    assert signal.reason == "loc_threshold"


def test_should_buy_uses_aggressive_mode_settings() -> None:
    strategy = DynamicWaveStrategy()
    context = make_context(
        effective_mode=StrategyMode.AGGRESSIVE,
        previous_close=Decimal("100"),
        current_close=Decimal("105"),
    )

    signal = strategy.should_buy(context)

    assert signal.should_buy is True
    assert signal.reason == "loc_threshold"


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


def test_position_size_uses_loc_limit_basis_for_safe_mode() -> None:
    strategy = DynamicWaveStrategy()
    size = strategy.calculate_position_size(
        make_context(previous_close=Decimal("100"), capital=Decimal("1000"), effective_mode=StrategyMode.SAFE)
    )

    assert size.amount == Decimal("142.857143")
    assert size.quantity == 1


def test_position_size_uses_loc_limit_basis_for_aggressive_mode() -> None:
    strategy = DynamicWaveStrategy()
    size = strategy.calculate_position_size(
        make_context(previous_close=Decimal("100"), capital=Decimal("1000"), effective_mode=StrategyMode.AGGRESSIVE)
    )

    assert size.amount == Decimal("142.857143")
    assert size.quantity == 1


def test_should_not_buy_when_cash_cannot_afford_capital_sized_quantity() -> None:
    strategy = DynamicWaveStrategy()
    context = make_context(capital=Decimal("1000"), cash=Decimal("50"), current_close=Decimal("103"))
    size = strategy.calculate_position_size(context)

    assert size.quantity == 1
    signal = strategy.should_buy(context)
    assert signal.should_buy is False
    assert signal.reason == "insufficient_cash"


def test_should_not_reduce_quantity_to_fit_cash() -> None:
    strategy = DynamicWaveStrategy()
    context = make_context(
        capital=Decimal("1000"),
        cash=Decimal("100"),
        current_close=Decimal("103"),
    )

    size = strategy.calculate_position_size(context)
    signal = strategy.should_buy(context)

    assert size.quantity == 1
    assert signal.should_buy is False
    assert signal.reason == "insufficient_cash"


def test_should_buy_and_position_size_agree_on_loc_quantity() -> None:
    strategy = DynamicWaveStrategy()
    context = make_context(
        previous_close=Decimal("100"),
        current_close=Decimal("103"),
        capital=Decimal("1000"),
        cash=Decimal("1000"),
        effective_mode=StrategyMode.SAFE,
    )

    signal = strategy.should_buy(context)
    size = strategy.calculate_position_size(context)

    assert signal.should_buy is True
    assert signal.reason == "loc_threshold"
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
    signal = strategy.should_sell(make_context(current_close=Decimal("100")), position)
    assert signal.should_sell is True
    assert signal.reason == "max_holding_period"


def test_update_capital_applies_pcr_and_lcr() -> None:
    strategy = DynamicWaveStrategy()
    context = make_context(capital=Decimal("1000"))
    assert strategy.update_capital(context, Decimal("100")).capital == Decimal("1060.000000")
    assert strategy.update_capital(context, Decimal("-100")).capital == Decimal("980.000000")


def test_registry_lists_creates_and_rejects_unknown_strategy_types() -> None:
    registry = StrategyRegistry()
    registry.register(DynamicWaveStrategy)

    assert registry.list() == [{"type": "dynamic_wave", "name": "Dynamic Wave Strategy"}]
    assert isinstance(registry.create("dynamic_wave"), DynamicWaveStrategy)

    try:
        registry.create("missing")
    except ValueError as exc:
        assert str(exc) == "Unknown strategy type 'missing'. Available strategy types: dynamic_wave"
    else:
        raise AssertionError("Expected ValueError for unknown strategy type")
