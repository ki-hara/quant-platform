import logging
from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.core.errors import MarketDataError
from app.dto.market_data import OhlcvDto


logger = logging.getLogger(__name__)

SEARCH_URL = "https://searchapi.eastmoney.com/api/suggest/get"
KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
PUBLIC_SEARCH_TOKEN = "D43BF722C8E33BDC906FB84D85E326E8"
US_MARKET_IDS = {"105", "106", "107"}


class EastmoneyMarketDataProvider:
    def __init__(self, http_get: Callable[..., Any] = httpx.get) -> None:
        self._http_get = http_get
        self._secids: dict[str, str] = {}

    def get_ohlcv(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[OhlcvDto]:
        if end_date <= start_date:
            return []

        normalized_symbol = symbol.upper()
        try:
            secid = self._resolve_secid(normalized_symbol)
            if secid is None:
                return []
            response = self._http_get(
                KLINE_URL,
                params={
                    "secid": secid,
                    "klt": "101",
                    "fqt": "0",
                    "beg": start_date.strftime("%Y%m%d"),
                    "end": (end_date - timedelta(days=1)).strftime("%Y%m%d"),
                    "fields1": "f1,f2,f3,f4,f5,f6",
                    "fields2": "f51,f52,f53,f54,f55,f56",
                },
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://quote.eastmoney.com/",
                },
                timeout=8.0,
            )
            response.raise_for_status()
            return self._parse_klines(
                response.json(),
                normalized_symbol,
                start_date,
                end_date,
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise MarketDataError(
                "market_data_provider_failed",
                "Eastmoney market data is unavailable.",
            ) from exc

    def _resolve_secid(self, symbol: str) -> str | None:
        cached = self._secids.get(symbol)
        if cached is not None:
            return cached

        response = self._http_get(
            SEARCH_URL,
            params={
                "input": symbol,
                "type": "14",
                "count": "10",
                "token": PUBLIC_SEARCH_TOKEN,
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://quote.eastmoney.com/",
            },
            timeout=8.0,
        )
        response.raise_for_status()
        rows = response.json().get("QuotationCodeTable", {}).get("Data") or []
        for row in rows:
            code = str(row.get("Code", "")).upper()
            quote_id = str(row.get("QuoteID", "")).upper()
            market_id, separator, quote_symbol = quote_id.partition(".")
            if (
                code == symbol
                and separator
                and quote_symbol == symbol
                and market_id in US_MARKET_IDS
            ):
                self._secids[symbol] = quote_id
                return quote_id
        return None

    @staticmethod
    def _parse_klines(
        payload: dict[str, Any],
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[OhlcvDto]:
        data = payload.get("data")
        if not isinstance(data, dict):
            return []
        if str(data.get("code", "")).upper() != symbol:
            return []

        prices: list[OhlcvDto] = []
        for raw_row in data.get("klines") or []:
            try:
                values = str(raw_row).split(",")
                quote_date = date.fromisoformat(values[0])
                open_price = Decimal(values[1])
                close = Decimal(values[2])
                high = Decimal(values[3])
                low = Decimal(values[4])
                volume_decimal = Decimal(values[5])
                numeric_values = (open_price, high, low, close, volume_decimal)
                valid_ohlc = (
                    all(value.is_finite() for value in numeric_values)
                    and min(open_price, high, low, close) > 0
                    and high >= max(open_price, close)
                    and low <= min(open_price, close)
                    and volume_decimal >= 0
                    and volume_decimal == volume_decimal.to_integral_value()
                )
                if not valid_ohlc or not start_date <= quote_date < end_date:
                    raise ValueError("invalid Eastmoney OHLCV row")
                prices.append(
                    OhlcvDto(
                        symbol=symbol,
                        date=quote_date,
                        open=open_price,
                        high=high,
                        low=low,
                        close=close,
                        volume=int(volume_decimal),
                        adjusted=False,
                    )
                )
            except (IndexError, InvalidOperation, TypeError, ValueError):
                logger.warning(
                    "Skipping invalid Eastmoney market data row: symbol=%s row=%s",
                    symbol,
                    raw_row,
                )
        return sorted(prices, key=lambda price: price.date)
