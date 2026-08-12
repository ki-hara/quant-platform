from datetime import UTC, date, datetime
from decimal import Decimal

from app.infrastructure.market_data.finnhub_regular_open_provider import (
    FinnhubRegularOpenProvider,
    parse_finnhub_regular_open,
)


def _timestamp(hour: int, minute: int) -> int:
    return int(datetime(2026, 8, 12, hour, minute, tzinfo=UTC).timestamp())


def test_parses_current_us_quote_open() -> None:
    result = parse_finnhub_regular_open(
        {"o": 147.31, "h": 147.70, "l": 144.15, "t": _timestamp(13, 37)},
        "SOXL",
        date(2026, 8, 12),
    )

    assert result.quote is not None
    assert result.quote.price == Decimal("147.31")
    assert result.quote.source == "finnhub_us_quote"


def test_missing_key_returns_diagnostic_without_network_call() -> None:
    calls = []
    provider = FinnhubRegularOpenProvider(
        api_key=None,
        http_get=lambda *args, **kwargs: calls.append((args, kwargs)),
        now=lambda: datetime(2026, 8, 12, 13, 31, tzinfo=UTC),
    )

    result = provider.get_open("SOXL", date(2026, 8, 12))

    assert result.failure_reason == "finnhub_api_key_missing"
    assert calls == []


def test_rejects_stale_and_impossible_quote() -> None:
    stale = parse_finnhub_regular_open(
        {"o": 147.31, "h": 147.70, "l": 144.15, "t": _timestamp(13, 29)},
        "SOXL",
        date(2026, 8, 12),
    )
    impossible = parse_finnhub_regular_open(
        {"o": 136.26, "h": 147.70, "l": 142.65, "t": _timestamp(13, 37)},
        "SOXL",
        date(2026, 8, 12),
    )

    assert stale.failure_reason == "opening_price_quote_stale"
    assert impossible.failure_reason == "opening_bar_ohlc_invalid"
