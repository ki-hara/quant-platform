from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import date
from decimal import Decimal
from threading import Lock
from time import monotonic
from typing import Protocol

from app.infrastructure.market_data.regular_open import RegularOpenLookup


MAX_ACCEPTABLE_DIFFERENCE = Decimal("0.05")
PROVIDER_WAIT_SECONDS = 1.5
MIN_REFRESH_SECONDS = 2.0
PEER_GRACE_SECONDS = 0.05


class RegularOpenProvider(Protocol):
    def get_open(self, symbol: str, session_date: date) -> RegularOpenLookup: ...


class ResilientRegularOpenProvider:
    def __init__(
        self,
        cnbc_provider: RegularOpenProvider,
        finnhub_provider: RegularOpenProvider,
        *,
        wait_seconds: float = PROVIDER_WAIT_SECONDS,
        refresh_seconds: float = MIN_REFRESH_SECONDS,
        clock=monotonic,
    ) -> None:
        self._cnbc_provider = cnbc_provider
        self._finnhub_provider = finnhub_provider
        self._wait_seconds = wait_seconds
        self._refresh_seconds = refresh_seconds
        self._clock = clock
        self._lookup_lock = Lock()
        self._last_raw_lookup: dict[
            tuple[str, date], tuple[int, float, RegularOpenLookup, RegularOpenLookup]
        ] = {}
        self._lookup_generation = 0
        self._last_disagreement: dict[
            tuple[str, date], tuple[tuple[Decimal, Decimal], int]
        ] = {}

    def get_open(self, symbol: str, session_date: date) -> RegularOpenLookup:
        key = (symbol.upper(), session_date)
        with self._lookup_lock:
            observed_at = self._clock()
            cached = self._last_raw_lookup.get(key)
            if cached is None or observed_at - cached[1] >= self._refresh_seconds:
                cnbc, finnhub = self._parallel_lookup(symbol, session_date)
                self._lookup_generation += 1
                generation = self._lookup_generation
                self._last_raw_lookup[key] = (generation, observed_at, cnbc, finnhub)
            else:
                generation, _, cnbc, finnhub = cached
            return self._arbitrate(key, generation, cnbc, finnhub)

    def _parallel_lookup(
        self, symbol: str, session_date: date
    ) -> tuple[RegularOpenLookup, RegularOpenLookup]:
        executor = ThreadPoolExecutor(max_workers=2)
        futures: dict[Future[RegularOpenLookup], str] = {
            executor.submit(
                self._safe_lookup, self._cnbc_provider, symbol, session_date
            ): "cnbc",
            executor.submit(
                self._safe_lookup, self._finnhub_provider, symbol, session_date
            ): "finnhub",
        }
        results: dict[str, RegularOpenLookup] = {}
        try:
            done, pending = wait(
                futures,
                timeout=self._wait_seconds,
                return_when=FIRST_COMPLETED,
            )
            self._collect(done, futures, results)

            if pending:
                any_valid = any(result.quote is not None for result in results.values())
                peer_wait = (
                    min(self._wait_seconds, PEER_GRACE_SECONDS)
                    if any_valid
                    else self._wait_seconds
                )
                more_done, pending = wait(pending, timeout=peer_wait)
                self._collect(more_done, futures, results)

            for future in pending:
                future.cancel()
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        return (
            results.get("cnbc")
            or RegularOpenLookup(None, "cnbc_quote_timeout"),
            results.get("finnhub")
            or RegularOpenLookup(None, "finnhub_quote_timeout"),
        )

    @staticmethod
    def _collect(
        done: set[Future[RegularOpenLookup]],
        futures: dict[Future[RegularOpenLookup], str],
        results: dict[str, RegularOpenLookup],
    ) -> None:
        for future in done:
            results[futures[future]] = future.result()

    def _arbitrate(
        self,
        key: tuple[str, date],
        generation: int,
        cnbc: RegularOpenLookup,
        finnhub: RegularOpenLookup,
    ) -> RegularOpenLookup:
        if cnbc.quote is None and finnhub.quote is None:
            self._last_disagreement.pop(key, None)
            reasons = ",".join(
                reason
                for reason in (cnbc.failure_reason, finnhub.failure_reason)
                if reason
            )
            return RegularOpenLookup(
                None, f"opening_price_sources_unavailable:{reasons}"
            )
        if cnbc.quote is None:
            self._last_disagreement.pop(key, None)
            return finnhub
        if finnhub.quote is None:
            self._last_disagreement.pop(key, None)
            return cnbc

        difference = abs(cnbc.quote.price - finnhub.quote.price)
        if difference <= MAX_ACCEPTABLE_DIFFERENCE:
            self._last_disagreement.pop(key, None)
            return cnbc

        signature = (cnbc.quote.price, finnhub.quote.price)
        previous = self._last_disagreement.get(key)
        if previous is not None and previous[0] == signature and previous[1] < generation:
            self._last_disagreement.pop(key, None)
            return cnbc
        if previous is None or previous[1] != generation:
            self._last_disagreement[key] = (signature, generation)
        return RegularOpenLookup(
            None,
            f"opening_price_sources_disagree:{cnbc.quote.price}:{finnhub.quote.price}",
        )

    @staticmethod
    def _safe_lookup(
        provider: RegularOpenProvider, symbol: str, session_date: date
    ) -> RegularOpenLookup:
        try:
            return provider.get_open(symbol, session_date)
        except Exception:  # Provider isolation is the boundary of this composite.
            return RegularOpenLookup(None, "opening_price_provider_exception")
