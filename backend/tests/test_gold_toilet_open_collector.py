import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.seed import seed_default_owner
from app.infrastructure.market_data.regular_open import (
    RegularOpenLookup,
    RegularSessionOpen,
)
from app.infrastructure.repositories.gold_toilet_orders import GoldToiletOrderRepository
from app.services.gold_toilet_open_collector import (
    GoldToiletOpenCollector,
    capture_window_start,
)
from app.main import create_app


class FakeProvider:
    def __init__(self, lookups: list[RegularOpenLookup]) -> None:
        self.lookups = lookups
        self.calls = 0

    def get_open(self, symbol: str, session_date: date) -> RegularOpenLookup:
        lookup = self.lookups[min(self.calls, len(self.lookups) - 1)]
        self.calls += 1
        return lookup


def _ready_lookup(
    price: str = "131.505", source: str = "cnbc_us_quote"
) -> RegularOpenLookup:
    return RegularOpenLookup(
        RegularSessionOpen(
            symbol="SOXL",
            session_date=date(2026, 8, 4),
            price=Decimal(price),
            high=None,
            low=None,
            bar_time=datetime(2026, 8, 4, 9, 30),
            source=source,
        )
    )


def _engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_default_owner(session, "default")
        GoldToiletOrderRepository(session).save_sheet(
            owner_id="default",
            order_date=date(2026, 8, 4),
            entry_percent=Decimal("1.49"),
            allocation_percent=Decimal("22.5"),
            loc_percent=Decimal("-9.34"),
        )
        session.commit()
    return engine


def test_capture_window_starts_five_seconds_before_open_in_edt_and_est() -> None:
    assert capture_window_start(date(2026, 8, 4)).astimezone(UTC) == datetime(
        2026, 8, 4, 13, 29, 55, tzinfo=UTC
    )
    assert capture_window_start(date(2026, 11, 3)).astimezone(UTC) == datetime(
        2026, 11, 3, 14, 29, 55, tzinfo=UTC
    )


def test_collector_captures_saved_sheet_without_an_api_request_and_only_once() -> None:
    engine = _engine()
    provider = FakeProvider([_ready_lookup(), _ready_lookup("999")])
    collector = GoldToiletOpenCollector(
        session_factory=lambda: Session(engine),
        market_provider=provider,
        now=lambda: datetime(2026, 8, 4, 13, 30, tzinfo=UTC),
    )

    assert collector.capture_once() is True
    assert collector.capture_once() is False

    with Session(engine) as session:
        sheet = GoldToiletOrderRepository(session).get_sheet("default", date(2026, 8, 4))
        assert sheet is not None
        assert sheet.provider_market_open == Decimal("131.505000")
        assert sheet.provider_open_source == "cnbc_us_quote"
    assert provider.calls == 1


def test_collector_retries_provider_failure_on_next_tick() -> None:
    engine = _engine()
    provider = FakeProvider(
        [RegularOpenLookup(None, "opening_bar_not_available"), _ready_lookup()]
    )
    collector = GoldToiletOpenCollector(
        session_factory=lambda: Session(engine),
        market_provider=provider,
        now=lambda: datetime(2026, 8, 4, 13, 30, tzinfo=UTC),
    )

    assert collector.capture_once() is False
    assert collector.capture_once() is True
    assert provider.calls == 2


def test_collector_waits_until_dst_aware_capture_window() -> None:
    engine = _engine()
    provider = FakeProvider([RegularOpenLookup(None, "regular_session_not_started")])
    now = capture_window_start(date(2026, 8, 4)) - timedelta(seconds=1)
    collector = GoldToiletOpenCollector(
        session_factory=lambda: Session(engine),
        market_provider=provider,
        now=lambda: now,
    )

    assert collector.capture_once() is False
    assert provider.calls == 0


def test_fastapi_lifespan_starts_and_stops_collector() -> None:
    class FakeCollector:
        def __init__(self) -> None:
            self.started = False
            self.cancelled = False

        async def run(self) -> None:
            self.started = True
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled = True
                raise

    engine = _engine()
    collector = FakeCollector()
    app = create_app(
        database_engine=engine,
        session_factory=lambda: Session(engine),
        gold_toilet_collector=collector,
    )

    with TestClient(app):
        assert collector.started is True
    assert collector.cancelled is True
