from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.infrastructure.market_data.yahoo_regular_open_provider import (
    parse_regular_session_open,
)


NEW_YORK = ZoneInfo("America/New_York")


def _timestamp(hour: int, minute: int) -> int:
    return int(datetime(2026, 8, 4, hour, minute, tzinfo=NEW_YORK).timestamp())


def _payload(
    *,
    timestamps: list[int],
    opens: list[float | None],
    highs: list[float | None],
    lows: list[float | None],
) -> dict:
    return {
        "chart": {
            "result": [
                {
                    "timestamp": timestamps,
                    "indicators": {
                        "quote": [
                            {
                                "open": opens,
                                "high": highs,
                                "low": lows,
                                "close": opens,
                                "volume": [100] * len(timestamps),
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }


def test_extracts_only_0930_new_york_bar() -> None:
    result = parse_regular_session_open(
        _payload(
            timestamps=[_timestamp(9, 29), _timestamp(9, 30)],
            opens=[131.26, 131.505],
            highs=[131.64, 133.04],
            lows=[131.21, 129.66],
        ),
        "SOXL",
        date(2026, 8, 4),
    )

    assert result.quote is not None
    assert result.quote.price == Decimal("131.505")
    assert result.quote.high == Decimal("133.04")
    assert result.quote.low == Decimal("129.66")
    assert result.quote.bar_time.isoformat() == "2026-08-04T09:30:00-04:00"
    assert result.failure_reason is None


def test_rejects_observed_daily_candle_style_impossible_open() -> None:
    result = parse_regular_session_open(
        _payload(
            timestamps=[_timestamp(9, 30)],
            opens=[106.15],
            highs=[133.04],
            lows=[129.66],
        ),
        "SOXL",
        date(2026, 8, 4),
    )

    assert result.quote is None
    assert result.failure_reason == "opening_bar_ohlc_invalid"


def test_returns_waiting_reason_before_0930_bar_exists() -> None:
    result = parse_regular_session_open(
        _payload(
            timestamps=[_timestamp(9, 29)],
            opens=[131.26],
            highs=[131.64],
            lows=[131.21],
        ),
        "SOXL",
        date(2026, 8, 4),
    )

    assert result.quote is None
    assert result.failure_reason == "opening_bar_not_available"


def test_rejects_null_opening_bar_values() -> None:
    result = parse_regular_session_open(
        _payload(
            timestamps=[_timestamp(9, 30)],
            opens=[None],
            highs=[133.04],
            lows=[129.66],
        ),
        "SOXL",
        date(2026, 8, 4),
    )

    assert result.quote is None
    assert result.failure_reason == "opening_bar_values_missing"


def test_accepts_open_immediately_when_intraminute_high_and_low_are_missing() -> None:
    result = parse_regular_session_open(
        _payload(
            timestamps=[_timestamp(9, 30)],
            opens=[131.505],
            highs=[None],
            lows=[None],
        ),
        "SOXL",
        date(2026, 8, 4),
    )

    assert result.quote is not None
    assert result.quote.price == Decimal("131.505")
    assert result.quote.high is None
    assert result.quote.low is None
    assert result.failure_reason is None


def test_rejects_non_finite_opening_bar_values() -> None:
    result = parse_regular_session_open(
        _payload(
            timestamps=[_timestamp(9, 30)],
            opens=[float("nan")],
            highs=[133.04],
            lows=[129.66],
        ),
        "SOXL",
        date(2026, 8, 4),
    )

    assert result.quote is None
    assert result.failure_reason == "opening_bar_values_invalid"
