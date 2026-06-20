from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Sequence

from app.domain.enums import StrategyMode

RSI_PERIOD = 14
TRADING_DAYS_PER_WEEK = 5


@dataclass(frozen=True)
class DailyClose:
    date: date
    close: Decimal


@dataclass(frozen=True)
class WeeklyClose:
    week_ending: date
    close: Decimal
    data_as_of: date


@dataclass(frozen=True)
class WeeklyRsiTransition:
    effective_week: date
    previous_rsi: Decimal
    current_rsi: Decimal
    recommended_mode: StrategyMode
    rule_code: str | None
    data_as_of: date


def aggregate_daily_closes_to_weekly_closes(daily_closes: Sequence[DailyClose]) -> list[WeeklyClose]:
    latest_close_by_week_start: dict[date, DailyClose] = {}
    for daily_close in sorted(daily_closes, key=lambda item: item.date):
        week_start = daily_close.date - timedelta(days=daily_close.date.weekday())
        latest_close_by_week_start[week_start] = daily_close

    weekly_closes: list[WeeklyClose] = []
    for week_start in sorted(latest_close_by_week_start):
        latest_close = latest_close_by_week_start[week_start]
        weekly_closes.append(
            WeeklyClose(
                week_ending=week_start + timedelta(days=TRADING_DAYS_PER_WEEK - 1),
                close=latest_close.close,
                data_as_of=latest_close.date,
            )
        )
    return weekly_closes


def calculate_simple_rsi(closes: Sequence[Decimal]) -> Decimal | None:
    if len(closes) < RSI_PERIOD + 1:
        return None

    window = list(closes)[- (RSI_PERIOD + 1) :]
    total_gain = Decimal("0")
    total_loss = Decimal("0")

    for previous_close, current_close in zip(window[:-1], window[1:]):
        delta = current_close - previous_close
        if delta > 0:
            total_gain += delta
        elif delta < 0:
            total_loss += -delta

    avg_gain = total_gain / Decimal(RSI_PERIOD)
    avg_loss = total_loss / Decimal(RSI_PERIOD)

    if avg_gain == 0 and avg_loss == 0:
        return Decimal("50")
    if avg_loss == 0:
        return Decimal("100")

    relative_strength = avg_gain / avg_loss
    return Decimal("100") - (Decimal("100") / (Decimal("1") + relative_strength))


def resolve_weekly_rsi_mode_transition(
    *,
    previous_rsi: Decimal,
    current_rsi: Decimal,
    prior_mode: StrategyMode,
    effective_week: date,
    data_as_of: date,
) -> WeeklyRsiTransition:
    recommended_mode = prior_mode
    rule_code: str | None = None

    if previous_rsi >= Decimal("65") and current_rsi < previous_rsi:
        recommended_mode = StrategyMode.SAFE
        rule_code = "S1"
    elif Decimal("40") <= previous_rsi <= Decimal("50") and current_rsi < previous_rsi:
        recommended_mode = StrategyMode.SAFE
        rule_code = "S2"
    elif previous_rsi >= Decimal("50") and current_rsi < Decimal("50"):
        recommended_mode = StrategyMode.SAFE
        rule_code = "S3"
    elif previous_rsi <= Decimal("50") and current_rsi > Decimal("50"):
        recommended_mode = StrategyMode.AGGRESSIVE
        rule_code = "A1"
    elif Decimal("50") <= previous_rsi <= Decimal("60") and current_rsi > previous_rsi:
        recommended_mode = StrategyMode.AGGRESSIVE
        rule_code = "A2"
    elif previous_rsi <= Decimal("35") and current_rsi > previous_rsi:
        recommended_mode = StrategyMode.AGGRESSIVE
        rule_code = "A3"

    return WeeklyRsiTransition(
        effective_week=effective_week,
        previous_rsi=previous_rsi,
        current_rsi=current_rsi,
        recommended_mode=recommended_mode,
        rule_code=rule_code,
        data_as_of=data_as_of,
    )


def resolve_weekly_rsi_transition(
    weekly_closes: Sequence[WeeklyClose],
    *,
    prior_mode: StrategyMode,
) -> WeeklyRsiTransition | None:
    if len(weekly_closes) < RSI_PERIOD + 2:
        return None

    recent_weekly_closes = sorted(weekly_closes, key=lambda item: item.week_ending)[-(RSI_PERIOD + 2) :]
    previous_rsi = calculate_simple_rsi([weekly_close.close for weekly_close in recent_weekly_closes[:-1]])
    current_rsi = calculate_simple_rsi([weekly_close.close for weekly_close in recent_weekly_closes[1:]])
    if previous_rsi is None or current_rsi is None:
        return None

    current_week = recent_weekly_closes[-1]
    effective_week = current_week.week_ending + timedelta(days=3)
    return resolve_weekly_rsi_mode_transition(
        previous_rsi=previous_rsi,
        current_rsi=current_rsi,
        prior_mode=prior_mode,
        effective_week=effective_week,
        data_as_of=current_week.data_as_of,
    )
