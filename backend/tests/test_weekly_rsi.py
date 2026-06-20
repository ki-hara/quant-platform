from datetime import date
from decimal import Decimal

import pytest

from app.domain.enums import StrategyMode
from app.strategy_engine.weekly_rsi import (
    DailyClose,
    WeeklyClose,
    WeeklyRsiTransition,
    aggregate_daily_closes_to_weekly_closes,
    calculate_simple_rsi,
    resolve_weekly_rsi_mode_transition,
    resolve_weekly_rsi_transition,
)


def make_daily_close(day: date, close: str) -> DailyClose:
    return DailyClose(date=day, close=Decimal(close))


def make_weekly_close(week_ending: date, close: str, data_as_of: date) -> WeeklyClose:
    return WeeklyClose(week_ending=week_ending, close=Decimal(close), data_as_of=data_as_of)


def test_calculate_simple_rsi_returns_none_when_fewer_than_15_closes() -> None:
    closes = [Decimal(str(value)) for value in range(100, 114)]

    assert calculate_simple_rsi(closes) is None


def test_calculate_simple_rsi_returns_50_when_average_gain_and_loss_are_zero() -> None:
    closes = [Decimal("100")] * 15

    assert calculate_simple_rsi(closes) == Decimal("50")


def test_calculate_simple_rsi_returns_100_when_average_loss_is_zero() -> None:
    closes = [Decimal(str(value)) for value in range(100, 115)]

    assert calculate_simple_rsi(closes) == Decimal("100")


def test_aggregate_daily_closes_to_weekly_closes_is_holiday_safe() -> None:
    daily_closes = [
        make_daily_close(date(2026, 1, 5), "100"),
        make_daily_close(date(2026, 1, 6), "101"),
        make_daily_close(date(2026, 1, 7), "102"),
        make_daily_close(date(2026, 1, 8), "103"),
        make_daily_close(date(2026, 1, 12), "110"),
        make_daily_close(date(2026, 1, 13), "111"),
        make_daily_close(date(2026, 1, 14), "112"),
        make_daily_close(date(2026, 1, 15), "113"),
        make_daily_close(date(2026, 1, 16), "114"),
    ]

    weekly_closes = aggregate_daily_closes_to_weekly_closes(daily_closes)

    assert weekly_closes == [
        WeeklyClose(week_ending=date(2026, 1, 9), close=Decimal("103"), data_as_of=date(2026, 1, 8)),
        WeeklyClose(week_ending=date(2026, 1, 16), close=Decimal("114"), data_as_of=date(2026, 1, 16)),
    ]


@pytest.mark.parametrize(
    "previous_rsi,current_rsi,prior_mode,expected_mode,expected_rule",
    [
        (Decimal("65"), Decimal("64.9"), StrategyMode.AGGRESSIVE, StrategyMode.SAFE, "S1"),
        (Decimal("40"), Decimal("39.9"), StrategyMode.AGGRESSIVE, StrategyMode.SAFE, "S2"),
        (Decimal("50"), Decimal("49.9"), StrategyMode.AGGRESSIVE, StrategyMode.SAFE, "S2"),
        (Decimal("50"), Decimal("50.1"), StrategyMode.SAFE, StrategyMode.AGGRESSIVE, "A1"),
        (Decimal("50"), Decimal("50.1"), StrategyMode.AGGRESSIVE, StrategyMode.AGGRESSIVE, "A1"),
        (Decimal("35"), Decimal("35.1"), StrategyMode.SAFE, StrategyMode.AGGRESSIVE, "A3"),
        (Decimal("60"), Decimal("60.1"), StrategyMode.SAFE, StrategyMode.AGGRESSIVE, "A2"),
    ],
)
def test_resolve_weekly_rsi_mode_transition_applies_boundary_rules(
    previous_rsi: Decimal,
    current_rsi: Decimal,
    prior_mode: StrategyMode,
    expected_mode: StrategyMode,
    expected_rule: str,
) -> None:
    transition = resolve_weekly_rsi_mode_transition(
        previous_rsi=previous_rsi,
        current_rsi=current_rsi,
        prior_mode=prior_mode,
        effective_week=date(2026, 4, 6),
        data_as_of=date(2026, 4, 3),
    )

    assert transition.recommended_mode == expected_mode
    assert transition.rule_code == expected_rule
    assert transition.effective_week == date(2026, 4, 6)


def test_resolve_weekly_rsi_mode_transition_uses_aggressive_a1_for_the_exact_values() -> None:
    transition = resolve_weekly_rsi_mode_transition(
        previous_rsi=Decimal("49.3589779596"),
        current_rsi=Decimal("53.5996753027"),
        prior_mode=StrategyMode.SAFE,
        effective_week=date(2026, 4, 6),
        data_as_of=date(2026, 4, 3),
    )

    assert transition == WeeklyRsiTransition(
        effective_week=date(2026, 4, 6),
        previous_rsi=Decimal("49.3589779596"),
        current_rsi=Decimal("53.5996753027"),
        recommended_mode=StrategyMode.AGGRESSIVE,
        rule_code="A1",
        data_as_of=date(2026, 4, 3),
    )


def test_resolve_weekly_rsi_mode_transition_retains_prior_mode_when_no_rule_matches() -> None:
    transition = resolve_weekly_rsi_mode_transition(
        previous_rsi=Decimal("55"),
        current_rsi=Decimal("55"),
        prior_mode=StrategyMode.SAFE,
        effective_week=date(2026, 4, 6),
        data_as_of=date(2026, 4, 3),
    )

    assert transition.recommended_mode == StrategyMode.SAFE
    assert transition.rule_code is None
    assert transition.previous_rsi == Decimal("55")
    assert transition.current_rsi == Decimal("55")


def test_resolve_weekly_rsi_transition_requires_16_weekly_closes() -> None:
    transition = resolve_weekly_rsi_transition(
        [
            make_weekly_close(date(2025, 12, 19), "100", date(2025, 12, 19)),
            make_weekly_close(date(2025, 12, 26), "101", date(2025, 12, 26)),
            make_weekly_close(date(2026, 1, 2), "102", date(2026, 1, 2)),
            make_weekly_close(date(2026, 1, 9), "103", date(2026, 1, 9)),
            make_weekly_close(date(2026, 1, 16), "104", date(2026, 1, 16)),
            make_weekly_close(date(2026, 1, 23), "105", date(2026, 1, 23)),
            make_weekly_close(date(2026, 1, 30), "106", date(2026, 1, 30)),
            make_weekly_close(date(2026, 2, 6), "107", date(2026, 2, 6)),
            make_weekly_close(date(2026, 2, 13), "108", date(2026, 2, 13)),
            make_weekly_close(date(2026, 2, 20), "109", date(2026, 2, 20)),
            make_weekly_close(date(2026, 2, 27), "110", date(2026, 2, 27)),
            make_weekly_close(date(2026, 3, 6), "111", date(2026, 3, 6)),
            make_weekly_close(date(2026, 3, 13), "112", date(2026, 3, 13)),
            make_weekly_close(date(2026, 3, 20), "113", date(2026, 3, 20)),
            make_weekly_close(date(2026, 3, 27), "114", date(2026, 3, 27)),
        ],
        prior_mode=StrategyMode.SAFE,
    )

    assert transition is None


def test_resolve_weekly_rsi_transition_sets_effective_week_and_data_as_of() -> None:
    weekly_closes = [
        make_weekly_close(date(2025, 12, 19), "100", date(2025, 12, 19)),
        make_weekly_close(date(2025, 12, 26), "101", date(2025, 12, 26)),
        make_weekly_close(date(2026, 1, 2), "102", date(2026, 1, 2)),
        make_weekly_close(date(2026, 1, 9), "103", date(2026, 1, 9)),
        make_weekly_close(date(2026, 1, 16), "104", date(2026, 1, 16)),
        make_weekly_close(date(2026, 1, 23), "105", date(2026, 1, 23)),
        make_weekly_close(date(2026, 1, 30), "106", date(2026, 1, 30)),
        make_weekly_close(date(2026, 2, 6), "107", date(2026, 2, 6)),
        make_weekly_close(date(2026, 2, 13), "108", date(2026, 2, 13)),
        make_weekly_close(date(2026, 2, 20), "109", date(2026, 2, 20)),
        make_weekly_close(date(2026, 2, 27), "110", date(2026, 2, 27)),
        make_weekly_close(date(2026, 3, 6), "111", date(2026, 3, 6)),
        make_weekly_close(date(2026, 3, 13), "112", date(2026, 3, 13)),
        make_weekly_close(date(2026, 3, 20), "113", date(2026, 3, 20)),
        make_weekly_close(date(2026, 3, 27), "114", date(2026, 3, 27)),
        make_weekly_close(date(2026, 4, 3), "115", date(2026, 4, 3)),
    ]

    transition = resolve_weekly_rsi_transition(weekly_closes, prior_mode=StrategyMode.SAFE)

    assert transition == WeeklyRsiTransition(
        effective_week=date(2026, 4, 6),
        previous_rsi=Decimal("100"),
        current_rsi=Decimal("100"),
        recommended_mode=StrategyMode.SAFE,
        rule_code=None,
        data_as_of=date(2026, 4, 3),
    )
