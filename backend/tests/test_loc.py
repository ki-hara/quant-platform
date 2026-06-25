from decimal import Decimal

import pytest

from app.strategy_engine.loc import LocOrder, LocPlan, calculate_loc_plan


def test_calculate_loc_plan_returns_expected_values_for_exact_case() -> None:
    plan = calculate_loc_plan(
        previous_close=Decimal("100"),
        capital=Decimal("1000"),
        cash=Decimal("5"),
        fee_rate=Decimal("5"),
        split_count=5,
        buy_threshold_percent=5,
        open_position_count=0,
    )

    assert plan == LocPlan(
        limit_price=Decimal("105.000000"),
        allocation=Decimal("200.000000"),
        quantity=1,
        estimated_fee=Decimal("5.250000"),
        required_cash=Decimal("110.250000"),
        available=Decimal("5.000000"),
        blocking_reason="insufficient_cash",
        orders=[
            LocOrder(
                step=1,
                limit_price=Decimal("105.000000"),
                quantity=1,
                cumulative_quantity=1,
            ),
            LocOrder(
                step=2,
                limit_price=Decimal("100.000000"),
                quantity=1,
                cumulative_quantity=2,
            ),
        ],
    )


def test_calculate_loc_plan_blocks_when_split_limit_is_reached() -> None:
    plan = calculate_loc_plan(
        previous_close=Decimal("100"),
        capital=Decimal("1000"),
        cash=Decimal("1000"),
        fee_rate=Decimal("5"),
        split_count=2,
        buy_threshold_percent=5,
        open_position_count=2,
    )

    assert plan.blocking_reason == "split_limit_reached"


def test_calculate_loc_plan_blocks_when_quantity_is_zero() -> None:
    plan = calculate_loc_plan(
        previous_close=Decimal("1000"),
        capital=Decimal("100"),
        cash=Decimal("1000"),
        fee_rate=Decimal("5"),
        split_count=5,
        buy_threshold_percent=5,
        open_position_count=0,
    )

    assert plan.blocking_reason == "quantity_zero"
    assert plan.quantity == 0


def test_calculate_loc_plan_blocks_for_insufficient_cash_after_quantity_is_computed() -> None:
    plan = calculate_loc_plan(
        previous_close=Decimal("100"),
        capital=Decimal("1000"),
        cash=Decimal("100"),
        fee_rate=Decimal("5"),
        split_count=5,
        buy_threshold_percent=5,
        open_position_count=0,
    )

    assert plan.blocking_reason == "insufficient_cash"
    assert plan.quantity == 1
    assert plan.required_cash == Decimal("110.250000")


def test_calculate_loc_plan_does_not_reduce_quantity_to_fit_cash() -> None:
    plan = calculate_loc_plan(
        previous_close=Decimal("100"),
        capital=Decimal("1000"),
        cash=Decimal("100"),
        fee_rate=Decimal("5"),
        split_count=5,
        buy_threshold_percent=5,
        open_position_count=0,
    )

    assert plan.quantity == 1
    assert plan.required_cash == Decimal("110.250000")


@pytest.mark.parametrize("split_count", [0, -1])
def test_calculate_loc_plan_rejects_non_positive_split_count(split_count: int) -> None:
    with pytest.raises(ValueError, match="split_count_must_be_positive"):
        calculate_loc_plan(
            previous_close=Decimal("100"),
            capital=Decimal("1000"),
            cash=Decimal("1000"),
            fee_rate=Decimal("5"),
            split_count=split_count,
            buy_threshold_percent=5,
            open_position_count=0,
        )


def test_calculate_loc_plan_preserves_exact_six_decimal_boundary() -> None:
    plan = calculate_loc_plan(
        previous_close=Decimal("100.000001"),
        capital=Decimal("1000.000001"),
        cash=Decimal("1000.000001"),
        fee_rate=Decimal("5"),
        split_count=5,
        buy_threshold_percent=0,
        open_position_count=0,
    )

    assert plan.limit_price == Decimal("100.000001")
    assert plan.allocation == Decimal("200.000000")
    assert plan.estimated_fee == Decimal("5.000000")
    assert plan.required_cash == Decimal("105.000001")
