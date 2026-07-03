from datetime import date, timedelta
from decimal import Decimal

from app.strategy_engine.weekly_cci import DailyOhlc, classify_cci_trend, weekly_cci_series


def _daily_rows(start: date, weekly_typicals: list[Decimal]) -> list[DailyOhlc]:
    rows: list[DailyOhlc] = []
    for index, typical in enumerate(weekly_typicals):
        rows.append(
            DailyOhlc(
                date=start + timedelta(days=index * 7),
                high=typical,
                low=typical,
                close=typical,
            )
        )
    return rows


def test_weekly_cci_series_uses_30_week_period() -> None:
    points = weekly_cci_series(
        _daily_rows(date(2026, 1, 2), [Decimal("100")] * 29 + [Decimal("130")])
    )

    assert len(points) == 1
    assert points[0].date == date(2026, 7, 24)
    assert points[0].value > Decimal("0")


def test_classify_cci_trend_requires_two_negative_weeks_to_confirm_bearish() -> None:
    candidate = classify_cci_trend(
        [
            Decimal("12"),
            Decimal("-2"),
        ]
    )
    confirmed = classify_cci_trend(
        [
            Decimal("12"),
            Decimal("-2"),
            Decimal("-7"),
        ]
    )

    assert candidate.status == "bearish_candidate"
    assert candidate.label == "하락 전환 후보"
    assert candidate.streak == 1
    assert confirmed.status == "bearish_confirmed"
    assert confirmed.label == "하락장 확정"
    assert confirmed.streak == 2


def test_classify_cci_trend_requires_two_positive_weeks_to_confirm_bullish() -> None:
    candidate = classify_cci_trend(
        [
            Decimal("-12"),
            Decimal("2"),
        ]
    )
    confirmed = classify_cci_trend(
        [
            Decimal("-12"),
            Decimal("2"),
            Decimal("7"),
        ]
    )

    assert candidate.status == "bullish_candidate"
    assert candidate.label == "상승 전환 후보"
    assert candidate.streak == 1
    assert confirmed.status == "bullish_confirmed"
    assert confirmed.label == "상승장 유지"
    assert confirmed.streak == 2
