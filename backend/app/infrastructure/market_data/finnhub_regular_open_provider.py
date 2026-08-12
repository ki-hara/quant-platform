from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

import httpx

from app.infrastructure.market_data.regular_open import (
    RegularOpenLookup,
    RegularSessionOpen,
    is_current_regular_quote,
    parse_price,
    regular_session_started,
    validate_open_ohlc,
)


FINNHUB_QUOTE_URL = "https://finnhub.io/api/v1/quote"


class FinnhubRegularOpenProvider:
    def __init__(
        self,
        api_key: str | None,
        http_get: Callable[..., Any] = httpx.get,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._api_key = api_key
        self._http_get = http_get
        self._now = now or (lambda: datetime.now(UTC))

    def get_open(self, symbol: str, session_date: date) -> RegularOpenLookup:
        if not self._api_key:
            return RegularOpenLookup(None, "finnhub_api_key_missing")
        if not regular_session_started(session_date, self._now()):
            return RegularOpenLookup(None, "regular_session_not_started")
        try:
            response = self._http_get(
                FINNHUB_QUOTE_URL,
                params={"symbol": symbol},
                headers={"X-Finnhub-Token": self._api_key},
                timeout=5.0,
            )
            response.raise_for_status()
            return parse_finnhub_regular_open(response.json(), symbol, session_date)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return RegularOpenLookup(None, "finnhub_quote_unavailable")


def parse_finnhub_regular_open(
    payload: dict[str, Any], symbol: str, session_date: date
) -> RegularOpenLookup:
    try:
        bar_time = datetime.fromtimestamp(int(payload["t"]), tz=UTC)
    except (KeyError, TypeError, ValueError, OSError):
        return RegularOpenLookup(None, "opening_price_quote_time_invalid")
    if not is_current_regular_quote(bar_time, session_date):
        return RegularOpenLookup(None, "opening_price_quote_stale")

    open_price = parse_price(payload.get("o"))
    high = parse_price(payload.get("h"))
    low = parse_price(payload.get("l"))
    failure = validate_open_ohlc(open_price, high, low)
    if failure:
        return RegularOpenLookup(None, failure)
    assert open_price is not None
    return RegularOpenLookup(
        RegularSessionOpen(
            symbol=symbol.upper(),
            session_date=session_date,
            price=open_price,
            high=high,
            low=low,
            bar_time=bar_time,
            source="finnhub_us_quote",
        )
    )
