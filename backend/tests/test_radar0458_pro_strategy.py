from decimal import Decimal

from app.strategy_engine.radar0458_pro import (
    RADAR_PRESETS,
    Radar0458ProStrategy,
    build_radar_buy_plan,
    next_radar_tier,
)
from app.strategy_engine.registry import registry


def test_radar_presets_match_the_fixed_pro_rules() -> None:
    assert RADAR_PRESETS["pro1"].tier_ratios == (
        Decimal("0.05"),
        Decimal("0.10"),
        Decimal("0.15"),
        Decimal("0.20"),
        Decimal("0.25"),
        Decimal("0.25"),
    )
    assert RADAR_PRESETS["pro1"].buy_threshold_percent == Decimal("-0.01")
    assert RADAR_PRESETS["pro1"].sell_threshold_percent == Decimal("0.01")
    assert RADAR_PRESETS["pro1"].max_holding_days == 10
    assert RADAR_PRESETS["pro2"].sell_threshold_percent == Decimal("1.50")
    assert RADAR_PRESETS["pro3"].tier_ratios == (Decimal("1") / Decimal("6"),) * 6
    assert RADAR_PRESETS["pro3"].buy_threshold_percent == Decimal("-0.10")
    assert RADAR_PRESETS["pro3"].sell_threshold_percent == Decimal("2.00")
    assert RADAR_PRESETS["pro3"].max_holding_days == 12


def test_next_radar_tier_returns_lowest_empty_regular_tier_then_reserve() -> None:
    assert next_radar_tier({1, 3, 4}) == 2
    assert next_radar_tier({1, 2, 3, 4, 5, 6}) == 7
    assert next_radar_tier({1, 2, 3, 4, 5, 6, 7}) is None


def test_build_radar_buy_plan_rounds_limit_down_to_cents_and_floors_quantity() -> None:
    plan = build_radar_buy_plan(
        previous_close=Decimal("123.456"),
        cycle_capital=Decimal("10000"),
        available_cash=Decimal("5000"),
        occupied_tiers={1},
        profile="pro1",
    )
    assert plan.tier == 2
    assert plan.profile == "pro1"
    assert plan.cycle_capital == Decimal("10000")
    assert plan.limit_price == Decimal("123.44")
    assert plan.allocation == Decimal("1000.00")
    assert plan.quantity == 8
    assert plan.blocking_reason is None


def test_build_radar_buy_plan_uses_available_cash_for_reserve_tier() -> None:
    plan = build_radar_buy_plan(
        previous_close=Decimal("100"),
        cycle_capital=Decimal("10000"),
        available_cash=Decimal("349.99"),
        occupied_tiers={1, 2, 3, 4, 5, 6},
        profile="pro2",
    )
    assert plan.tier == 7
    assert plan.allocation == Decimal("349.99")
    assert plan.quantity == 3
    assert plan.blocking_reason is None


def test_radar_strategy_is_registered_with_profile_schema() -> None:
    strategy = registry.create("radar0458_pro")
    assert isinstance(strategy, Radar0458ProStrategy)
    assert strategy.strategy_type == "radar0458_pro"
    assert strategy.get_settings_schema() == {
        "type": "object",
        "fields": {
            "pro_profile": {
                "type": "string",
                "enum": ["pro1", "pro2", "pro3"],
                "default": "pro1",
            }
        },
    }
