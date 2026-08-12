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


CNBC_QUOTE_URL = (
    "https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol"
)


class CnbcRegularOpenProvider:
    def __init__(
        self,
        http_get: Callable[..., Any] = httpx.get,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._http_get = http_get
        self._now = now or (lambda: datetime.now(UTC))

    def get_open(self, symbol: str, session_date: date) -> RegularOpenLookup:
        if not regular_session_started(session_date, self._now()):
            return RegularOpenLookup(None, "regular_session_not_started")
        try:
            response = self._http_get(
                CNBC_QUOTE_URL,
                params={
                    "symbols": symbol,
                    "requestMethod": "quick",
                    "noform": "1",
                    "partnerId": "2",
                    "fund": "1",
                    "exthrs": "1",
                    "output": "json",
                },
                headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"},
                timeout=5.0,
            )
            response.raise_for_status()
            return parse_cnbc_regular_open(response.json(), symbol, session_date)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return RegularOpenLookup(None, "cnbc_quote_unavailable")


def parse_cnbc_regular_open(
    payload: dict[str, Any], symbol: str, session_date: date
) -> RegularOpenLookup:
    try:
        quote = payload["FormattedQuoteResult"]["FormattedQuote"][0]
    except (KeyError, IndexError, TypeError):
        return RegularOpenLookup(None, "opening_price_payload_invalid")

    if str(quote.get("symbol", "")).upper() != symbol.upper():
        return RegularOpenLookup(None, "opening_price_symbol_mismatch")
    provenance = str(quote.get("source", ""))
    trusted_last_sale = "NYSE Arca" in provenance or "NASDAQ LS" in provenance
    if not trusted_last_sale or "CTA" not in provenance:
        return RegularOpenLookup(None, "cnbc_quote_source_untrusted")

    try:
        bar_time = datetime.fromisoformat(str(quote["last_time"]))
    except (KeyError, TypeError, ValueError):
        return RegularOpenLookup(None, "opening_price_quote_time_invalid")
    if quote.get("curmktstatus") != "REG_MKT" or not is_current_regular_quote(
        bar_time, session_date
    ):
        return RegularOpenLookup(None, "regular_session_not_started")

    open_price = parse_price(quote.get("open"))
    high = parse_price(quote.get("high"))
    low = parse_price(quote.get("low"))
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
            source="cnbc_us_quote",
        )
    )
