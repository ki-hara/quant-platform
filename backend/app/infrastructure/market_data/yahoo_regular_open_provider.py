from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

import httpx


NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class RegularSessionOpen:
    symbol: str
    session_date: date
    price: Decimal
    high: Decimal | None
    low: Decimal | None
    bar_time: datetime


@dataclass(frozen=True)
class RegularOpenLookup:
    quote: RegularSessionOpen | None
    failure_reason: str | None = None


class YahooRegularOpenProvider:
    def __init__(
        self,
        http_get: Callable[..., Any] = httpx.get,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._http_get = http_get
        self._now = now or (lambda: datetime.now(UTC))

    def get_open(self, symbol: str, session_date: date) -> RegularOpenLookup:
        session_start = datetime.combine(session_date, time(9, 30), NEW_YORK)
        observed_at = self._now()
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)
        session_started = observed_at.astimezone(NEW_YORK) >= session_start

        try:
            response = self._http_get(
                f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}",
                params={
                    "period1": int((session_start - timedelta(days=1)).timestamp()),
                    "period2": int((session_start + timedelta(days=1)).timestamp()),
                    "interval": "1d",
                    "includePrePost": "false",
                    "cache_buster": int(observed_at.timestamp()),
                },
                headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"},
                timeout=5.0,
            )
            response.raise_for_status()
            if not session_started:
                return RegularOpenLookup(None, "regular_session_not_started")
            return parse_regular_session_open(response.json(), symbol, session_date)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return RegularOpenLookup(None, "opening_price_provider_unavailable")


def parse_regular_session_open(
    payload: dict[str, Any], symbol: str, session_date: date
) -> RegularOpenLookup:
    try:
        result = payload["chart"]["result"][0]
        timestamps = result.get("timestamp") or []
        quote = result["indicators"]["quote"][0]
        opens = quote.get("open") or []
        highs = quote.get("high") or []
        lows = quote.get("low") or []
    except (KeyError, IndexError, TypeError):
        return RegularOpenLookup(None, "opening_price_payload_invalid")

    for index, timestamp in enumerate(timestamps):
        bar_time = datetime.fromtimestamp(timestamp, tz=NEW_YORK)
        if bar_time.date() != session_date or bar_time.timetz().replace(tzinfo=None) < time(9, 30):
            continue
        if index >= len(opens):
            return RegularOpenLookup(None, "opening_bar_values_missing")
        if opens[index] is None:
            return RegularOpenLookup(None, "opening_bar_values_missing")
        high_value = highs[index] if index < len(highs) else None
        low_value = lows[index] if index < len(lows) else None
        try:
            open_price = Decimal(str(opens[index]))
            high = Decimal(str(high_value)) if high_value is not None else None
            low = Decimal(str(low_value)) if low_value is not None else None
        except InvalidOperation:
            return RegularOpenLookup(None, "opening_bar_values_invalid")
        available_values = (open_price,) + tuple(
            value for value in (high, low) if value is not None
        )
        if not all(value.is_finite() for value in available_values):
            return RegularOpenLookup(None, "opening_bar_values_invalid")
        if (
            open_price <= 0
            or (high is not None and (high <= 0 or open_price > high))
            or (low is not None and (low <= 0 or low > open_price))
        ):
            return RegularOpenLookup(None, "opening_bar_ohlc_invalid")
        return RegularOpenLookup(
            RegularSessionOpen(
                symbol=symbol,
                session_date=session_date,
                price=open_price,
                high=high,
                low=low,
                bar_time=bar_time,
            )
        )
    return RegularOpenLookup(None, "opening_bar_not_available")
