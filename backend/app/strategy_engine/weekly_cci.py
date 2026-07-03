from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Sequence


CCI_PERIOD = 30
CCI_QUANT = Decimal("0.000001")


@dataclass(frozen=True)
class DailyOhlc:
    date: date
    high: Decimal
    low: Decimal
    close: Decimal


@dataclass(frozen=True)
class WeeklyCciPoint:
    date: date
    value: Decimal


@dataclass(frozen=True)
class CciTrend:
    status: str
    label: str
    streak: int
    risk_label: str


def weekly_cci_series(rows: Sequence[DailyOhlc], period: int = CCI_PERIOD) -> list[WeeklyCciPoint]:
    weekly_rows = _aggregate_daily_ohlc_to_weekly(rows)
    typical_prices = [(_row.high + _row.low + _row.close) / Decimal("3") for _row in weekly_rows]
    points: list[WeeklyCciPoint] = []
    for index in range(period - 1, len(weekly_rows)):
        window = typical_prices[index - period + 1 : index + 1]
        cci = _calculate_cci(window)
        if cci is not None:
            points.append(WeeklyCciPoint(date=weekly_rows[index].date, value=cci))
    return points


def classify_cci_trend(values: Sequence[Decimal]) -> CciTrend:
    non_null_values = [value for value in values if value is not None]
    if not non_null_values:
        return CciTrend("unavailable", "데이터 대기", 0, "판단 대기")

    latest_positive = non_null_values[-1] >= 0
    streak = 0
    for value in reversed(non_null_values):
        if (value >= 0) == latest_positive:
            streak += 1
        else:
            break

    if latest_positive and streak >= 2:
        return CciTrend("bullish_confirmed", "상승장 유지", streak, "전환 위험 낮음")
    if latest_positive:
        return CciTrend("bullish_candidate", "상승 전환 후보", streak, "확인 필요")
    if streak >= 2:
        return CciTrend("bearish_confirmed", "하락장 확정", streak, "방어 운용 권장")
    return CciTrend("bearish_candidate", "하락 전환 후보", streak, "전환 위험 높음")


def _calculate_cci(typical_prices: Sequence[Decimal]) -> Decimal | None:
    if not typical_prices:
        return None
    average = sum(typical_prices, Decimal("0")) / Decimal(len(typical_prices))
    mean_deviation = sum((abs(value - average) for value in typical_prices), Decimal("0")) / Decimal(len(typical_prices))
    if mean_deviation == 0:
        return Decimal("0").quantize(CCI_QUANT)
    return ((typical_prices[-1] - average) / (Decimal("0.015") * mean_deviation)).quantize(CCI_QUANT)


def _aggregate_daily_ohlc_to_weekly(rows: Sequence[DailyOhlc]) -> list[DailyOhlc]:
    buckets: dict[date, list[DailyOhlc]] = {}
    for row in sorted(rows, key=lambda item: item.date):
        week_ending = row.date + timedelta(days=(4 - row.date.weekday()) % 7)
        buckets.setdefault(week_ending, []).append(row)

    weekly_rows: list[DailyOhlc] = []
    for week_ending, week_rows in sorted(buckets.items()):
        weekly_rows.append(
            DailyOhlc(
                date=week_ending,
                high=max(row.high for row in week_rows),
                low=min(row.low for row in week_rows),
                close=week_rows[-1].close,
            )
        )
    return weekly_rows
