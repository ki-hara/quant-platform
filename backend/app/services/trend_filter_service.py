from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.core.config import settings
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.strategy_engine.weekly_cci import DailyOhlc, classify_cci_trend, weekly_cci_series


@dataclass(frozen=True)
class TrendFilterSymbol:
    symbol: str
    status: str
    label: str
    risk_label: str
    streak: int
    latest_cci: Decimal | None
    as_of: date | None
    zero_distance: Decimal | None


@dataclass(frozen=True)
class TrendFilterSummary:
    symbols: list[TrendFilterSymbol]
    summary: str


class TrendFilterService:
    def __init__(self, market_prices: MarketPriceRepository, provider: str | None = None) -> None:
        self.market_prices = market_prices
        self.provider = provider or settings.market_data_provider

    def get_summary(self, config_symbol: str, config_settings: dict, today: date) -> TrendFilterSummary:
        rows: list[TrendFilterSymbol] = []
        for symbol in trend_filter_symbols(config_settings, config_symbol):
            prices = self.market_prices.list_prices(self.provider, symbol, date.min, today)
            points = weekly_cci_series(
                [DailyOhlc(date=price.date, high=price.high, low=price.low, close=price.close) for price in prices]
            )
            trend = classify_cci_trend([point.value for point in points])
            latest = points[-1] if points else None
            rows.append(
                TrendFilterSymbol(
                    symbol=symbol,
                    status=trend.status,
                    label=trend.label,
                    risk_label=trend.risk_label,
                    streak=trend.streak,
                    latest_cci=latest.value if latest else None,
                    as_of=latest.date if latest else None,
                    zero_distance=latest.value if latest else None,
                )
            )
        return TrendFilterSummary(symbols=rows, summary=_summary_label(rows))


def trend_filter_symbols(config_settings: dict, config_symbol: str) -> list[str]:
    raw_symbols = config_settings.get("trend_filter_symbols") if isinstance(config_settings, dict) else None
    if isinstance(raw_symbols, str):
        candidates = raw_symbols.split(",")
    elif isinstance(raw_symbols, list):
        candidates = raw_symbols
    else:
        candidates = [config_settings.get("mode_rsi_symbol", "QQQ"), config_symbol]
    symbols: list[str] = []
    for value in candidates:
        symbol = str(value).strip().upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols or ["QQQ", config_symbol.upper()]


def _summary_label(rows: list[TrendFilterSymbol]) -> str:
    statuses = {row.status for row in rows}
    if "bearish_confirmed" in statuses:
        return "하락장 확정 종목이 있어 방어 운용을 강하게 검토하세요."
    if "bearish_candidate" in statuses:
        return "하락 전환 후보가 있어 이번 주 종가 확인이 중요합니다."
    if "bullish_candidate" in statuses:
        return "상승 전환 후보가 있어 추가 확인이 필요합니다."
    if rows and statuses == {"bullish_confirmed"}:
        return "추세 필터 종목이 모두 상승장 유지 상태입니다."
    return "추세 데이터가 충분하지 않습니다."
