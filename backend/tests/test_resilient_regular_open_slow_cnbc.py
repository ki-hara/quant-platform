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


def test_returns_valid_finnhub_without_waiting_for_slow_cnbc() -> None:
    class SlowCnbc:
        def get_open(self, symbol: str, session_date: date) -> RegularOpenLookup:
            sleep(0.3)
            return _ready("147.30", "cnbc_us_quote")

    class ReadyFinnhub:
        def get_open(self, symbol: str, session_date: date) -> RegularOpenLookup:
            return _ready("147.31", "finnhub_us_quote")

    provider = ResilientRegularOpenProvider(
        SlowCnbc(), ReadyFinnhub(), wait_seconds=0.2
    )

    started = monotonic()
    result = provider.get_open("SOXL", SESSION_DATE)

    assert monotonic() - started < 0.15
    assert result.quote is not None
    assert result.quote.source == "finnhub_us_quote"
