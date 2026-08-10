import asyncio
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.infrastructure.market_data.yahoo_regular_open_provider import RegularOpenLookup
from app.infrastructure.repositories.gold_toilet_orders import GoldToiletOrderRepository


NEW_YORK = ZoneInfo("America/New_York")
CAPTURE_LEAD = timedelta(seconds=5)
POLL_INTERVAL_SECONDS = 1.0


class MarketProvider(Protocol):
    def get_open(self, symbol: str, session_date: date) -> RegularOpenLookup: ...


def regular_session_start(session_date: date) -> datetime:
    return datetime.combine(session_date, time(9, 30), NEW_YORK)


def capture_window_start(session_date: date) -> datetime:
    return regular_session_start(session_date) - CAPTURE_LEAD


def capture_window_end(session_date: date) -> datetime:
    return datetime.combine(session_date, time(16, 0), NEW_YORK)


class GoldToiletOpenCollector:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        market_provider: MarketProvider,
        now: Callable[[], datetime] | None = None,
        poll_interval_seconds: float = POLL_INTERVAL_SECONDS,
    ) -> None:
        self._session_factory = session_factory
        self._market_provider = market_provider
        self._now = now or (lambda: datetime.now(UTC))
        self._poll_interval_seconds = poll_interval_seconds

    def capture_once(self) -> bool:
        observed_at = self._aware_now()
        session_date = observed_at.astimezone(NEW_YORK).date()
        if not (
            capture_window_start(session_date)
            <= observed_at.astimezone(NEW_YORK)
            < capture_window_end(session_date)
        ):
            return False

        with self._session_factory() as session:
            repository = GoldToiletOrderRepository(session)
            sheets = repository.list_unresolved_sheets(session_date)
            if not sheets:
                return False

            lookup = self._market_provider.get_open("SOXL", session_date)
            checked_at = observed_at.astimezone(UTC).replace(tzinfo=None)
            for sheet in sheets:
                if lookup.quote is None:
                    repository.record_provider_failure(
                        sheet,
                        lookup.failure_reason or "opening_price_provider_unavailable",
                        checked_at,
                    )
                else:
                    repository.snapshot_provider_open(sheet, lookup.quote.price, checked_at)
            session.commit()
            return lookup.quote is not None

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            started_at = loop.time()
            await asyncio.to_thread(self.capture_once)
            elapsed = loop.time() - started_at
            await asyncio.sleep(max(0.0, self._poll_interval_seconds - elapsed))

    def _aware_now(self) -> datetime:
        value = self._now()
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value
