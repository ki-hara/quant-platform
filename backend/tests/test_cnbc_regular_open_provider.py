from datetime import UTC, date, datetime
from decimal import Decimal

from app.infrastructure.market_data.cnbc_regular_open_provider import (
    CnbcRegularOpenProvider,
    parse_cnbc_regular_open,
)


def _payload(**overrides) -> dict:
    quote = {
        "symbol": "SOXL",
        "open": "147.30",
        "high": "147.70",
        "low": "144.15",
        "last_time": "2026-08-12T09:37:47.918-0400",
        "curmktstatus": "REG_MKT",
        "source": "Last NYSE Arca, VOL From CTA",
    }
    quote.update(overrides)
    return {"FormattedQuoteResult": {"FormattedQuote": [quote]}}


def test_parses_current_nyse_arca_regular_open() -> None:
    result = parse_cnbc_regular_open(_payload(), "SOXL", date(2026, 8, 12))

    assert result.quote is not None
    assert result.quote.price == Decimal("147.30")
    assert result.quote.source == "cnbc_us_quote"
    assert result.failure_reason is None


def test_rejects_pre_open_response() -> None:
    result = parse_cnbc_regular_open(
        _payload(curmktstatus="PRE_MKT", last_time="2026-08-12T09:29:59.000-0400"),
        "SOXL",
        date(2026, 8, 12),
    )

    assert result.quote is None
    assert result.failure_reason == "regular_session_not_started"


def test_rejects_wrong_symbol_and_impossible_ohlc() -> None:
    wrong_symbol = parse_cnbc_regular_open(
        _payload(symbol="TQQQ"), "SOXL", date(2026, 8, 12)
    )
    impossible = parse_cnbc_regular_open(
        _payload(open="136.26", low="142.65"), "SOXL", date(2026, 8, 12)
    )

    assert wrong_symbol.failure_reason == "opening_price_symbol_mismatch"
    assert impossible.failure_reason == "opening_bar_ohlc_invalid"


def test_provider_does_not_accept_before_session_start() -> None:
    calls = []

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("network must not be called before the session")

    provider = CnbcRegularOpenProvider(
        http_get=fake_get,
        now=lambda: datetime(2026, 8, 12, 13, 29, 59, tzinfo=UTC),
    )

    result = provider.get_open("SOXL", date(2026, 8, 12))

    assert result.failure_reason == "regular_session_not_started"
    assert calls == []
