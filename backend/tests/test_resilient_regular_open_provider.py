from datetime import date, datetime
from decimal import Decimal
from time import monotonic, sleep

from app.infrastructure.market_data.regular_open import (
    RegularOpenLookup,
    RegularSessionOpen,
)
from app.infrastructure.market_data.resilient_regular_open_provider import (
    ResilientRegularOpenProvider,
)


SESSION_DATE = date(2026, 8, 12)


class FakeProvider:
    def __init__(self, lookup: RegularOpenLookup) -> None:
        self.lookup = lookup
        self.calls = 0

    def get_open(self, symbol: str, session_date: date) -> RegularOpenLookup:
        self.calls += 1
        return self.lookup


def _ready(price: str, source: str) -> RegularOpenLookup:
    return RegularOpenLookup(
        RegularSessionOpen(
            symbol="SOXL",
            session_date=SESSION_DATE,
            price=Decimal(price),
            high=Decimal("150"),
            low=Decimal("140"),
            bar_time=datetime(2026, 8, 12, 9, 31),
            source=source,
        )
    )


def _provider(cnbc: RegularOpenLookup, finnhub: RegularOpenLookup):
    return ResilientRegularOpenProvider(FakeProvider(cnbc), FakeProvider(finnhub))


def test_uses_cnbc_when_finnhub_fails() -> None:
    provider = _provider(
        _ready("147.30", "cnbc_us_quote"),
        RegularOpenLookup(None, "finnhub_quote_unavailable"),
    )

    result = provider.get_open("SOXL", SESSION_DATE)

    assert result.quote is not None
    assert result.quote.source == "cnbc_us_quote"


def test_uses_finnhub_when_cnbc_fails() -> None:
    provider = _provider(
        RegularOpenLookup(None, "cnbc_quote_unavailable"),
        _ready("147.31", "finnhub_us_quote"),
    )

    result = provider.get_open("SOXL", SESSION_DATE)

    assert result.quote is not None
    assert result.quote.source == "finnhub_us_quote"


def test_prefers_cnbc_when_sources_are_within_five_cents() -> None:
    provider = _provider(
        _ready("147.30", "cnbc_us_quote"),
        _ready("147.34", "finnhub_us_quote"),
    )

    result = provider.get_open("SOXL", SESSION_DATE)

    assert result.quote is not None
    assert result.quote.price == Decimal("147.30")


def test_waits_one_cycle_then_bounds_persistent_large_disagreement() -> None:
    now = [100.0]
    provider = ResilientRegularOpenProvider(
        FakeProvider(_ready("147.30", "cnbc_us_quote")),
        FakeProvider(_ready("146.62", "finnhub_us_quote")),
        clock=lambda: now[0],
    )

    first = provider.get_open("SOXL", SESSION_DATE)
    cached = provider.get_open("SOXL", SESSION_DATE)
    now[0] += 2.0
    refreshed = provider.get_open("SOXL", SESSION_DATE)

    assert first.quote is None
    assert first.failure_reason == "opening_price_sources_disagree:147.30:146.62"
    assert cached.quote is None
    assert refreshed.quote is not None
    assert refreshed.quote.source == "cnbc_us_quote"


def test_returns_valid_source_without_waiting_for_slow_peer() -> None:
    class SlowProvider:
        def get_open(self, symbol: str, session_date: date) -> RegularOpenLookup:
            sleep(0.2)
            return _ready("147.31", "finnhub_us_quote")

    provider = ResilientRegularOpenProvider(
        FakeProvider(_ready("147.30", "cnbc_us_quote")),
        SlowProvider(),
        wait_seconds=0.02,
    )

    started = monotonic()
    result = provider.get_open("SOXL", SESSION_DATE)

    assert monotonic() - started < 0.15
    assert result.quote is not None
    assert result.quote.source == "cnbc_us_quote"


def test_coalesces_repeated_network_lookups_within_refresh_interval() -> None:
    now = [100.0]
    cnbc = FakeProvider(_ready("147.30", "cnbc_us_quote"))
    finnhub = FakeProvider(_ready("147.31", "finnhub_us_quote"))
    provider = ResilientRegularOpenProvider(cnbc, finnhub, clock=lambda: now[0])

    first = provider.get_open("SOXL", SESSION_DATE)
    now[0] += 1.0
    second = provider.get_open("SOXL", SESSION_DATE)

    assert first.quote is not None and second.quote is not None
    assert finnhub.calls == 1
    assert cnbc.calls == 1
