import logging
from time import perf_counter
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import MarketDataError
from app.dto.trading_plan import MarketRefreshResponseDto
from app.infrastructure.market_data.base import MarketDataProvider
from app.infrastructure.market_data.eastmoney_provider import EastmoneyMarketDataProvider
from app.infrastructure.market_data.finance_data_reader_provider import FinanceDataReaderProvider
from app.infrastructure.market_data.missing_daily_price_fallback_provider import (
    MissingDailyPriceFallbackProvider,
)
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.services.market_session_service import latest_confirmed_market_date
from app.services.mode_service import ModeService
from app.services.trend_filter_service import trend_filter_symbols


logger = logging.getLogger("uvicorn.error.market_refresh")


def get_market_data_provider() -> MarketDataProvider:
    return MissingDailyPriceFallbackProvider(
        FinanceDataReaderProvider(),
        EastmoneyMarketDataProvider(),
    )


class MarketRefreshService:
    def __init__(self, session: Session, provider: MarketDataProvider) -> None:
        self.session = session
        self.provider = provider
        self.configs = StrategyConfigRepository(session)
        self.market_prices = MarketPriceRepository(session)

    def refresh(self, config_id: int, today: date | None = None, full_history: bool = False) -> MarketRefreshResponseDto:
        config = self.configs.get(config_id)
        if config is None:
            raise ValueError(f"Strategy config not found: {config_id}")

        rsi_symbol = str(config.settings_json.get("mode_rsi_symbol", "QQQ"))
        investment_as_of = today or latest_confirmed_market_date(config.symbol)
        rsi_as_of = today or latest_confirmed_market_date(rsi_symbol)
        investment_prices = self._refresh_symbol(config.symbol, investment_as_of, full_history)
        warnings = []
        rsi_ok = True
        if rsi_symbol == config.symbol:
            rsi_prices = investment_prices
        else:
            try:
                rsi_prices = self._refresh_symbol(rsi_symbol, rsi_as_of, full_history)
            except MarketDataError as exc:
                rsi_ok = False
                warnings.append(f"{rsi_symbol}: {exc.message}")
                rsi_prices = self.market_prices.list_prices_up_to(settings.market_data_provider, rsi_symbol, rsi_as_of)
        for symbol in trend_filter_symbols(config.settings_json, config.symbol):
            if symbol not in {config.symbol, rsi_symbol}:
                try:
                    self._refresh_symbol(symbol, today or latest_confirmed_market_date(symbol), full_history)
                except MarketDataError as exc:
                    warnings.append(f"{symbol}: {exc.message}")

        modes = ModeService(self.session)
        recommendation = modes.get_mode_recommendation(config_id, as_of=rsi_as_of) if rsi_ok else None
        state = modes.get_state(config_id)
        return MarketRefreshResponseDto(
            confirmed_mode=state.confirmed_mode,
            confirmed_source=state.confirmed_source,
            recommended_mode=recommendation.recommended_mode if recommendation else None,
            differs=recommendation.differs if recommendation else False,
            warnings=warnings,
            investment_data_as_of=max((price.date for price in investment_prices), default=None),
            rsi_data_as_of=max((price.date for price in rsi_prices), default=None),
        )

    def _refresh_symbol(self, symbol: str, confirmed_as_of: date, full_history: bool = False) -> list:
        started = perf_counter()
        logger.info("Market refresh started: symbol=%s expected=%s", symbol, confirmed_as_of)
        start_date = confirmed_as_of - timedelta(days=400)
        latest = self.market_prices.latest_price_on_or_before(settings.market_data_provider, symbol, confirmed_as_of)
        history = self.market_prices.list_prices(settings.market_data_provider, symbol, start_date, confirmed_as_of)
        if latest is not None and len(history) >= 200 and not full_history:
            start_date = max(start_date, latest.date - timedelta(days=7))
        logger.info("Market refresh request: symbol=%s start=%s end=%s full_history=%s", symbol, start_date, confirmed_as_of, full_history)
        try:
            prices = self.provider.get_ohlcv(symbol, start_date, confirmed_as_of + timedelta(days=1))
        except MarketDataError as exc:
            logger.warning("Market history fetch failed: symbol=%s expected=%s code=%s", symbol, confirmed_as_of, exc.code)
            prices = []
        confirmed_prices = [price for price in prices if price.date <= confirmed_as_of]
        if not any(price.date == confirmed_as_of for price in confirmed_prices):
            try:
                retry_prices = self.provider.get_ohlcv(
                    symbol,
                    confirmed_as_of,
                    confirmed_as_of + timedelta(days=1),
                )
            except MarketDataError as exc:
                logger.warning(
                    "Confirmed market data retry failed: symbol=%s date=%s error=%s",
                    symbol,
                    confirmed_as_of,
                    exc.message,
                )
                retry_prices = []
            prices_by_date = {
                price.date: price
                for price in [*confirmed_prices, *retry_prices]
                if price.date <= confirmed_as_of
            }
            confirmed_prices = sorted(prices_by_date.values(), key=lambda price: price.date)

        if not any(price.date == confirmed_as_of for price in confirmed_prices):
            logger.warning("Market refresh incomplete: symbol=%s expected=%s elapsed_ms=%.0f", symbol, confirmed_as_of, (perf_counter()-started)*1000)
            raise MarketDataError(
                "market_data_incomplete",
                (
                    f"확정 거래일 {confirmed_as_of.isoformat()}의 {symbol} 시세가 "
                    "아직 완성되지 않았습니다. 잠시 후 다시 갱신해 주세요."
                ),
            )

        fetched_at = perf_counter()
        self.market_prices.upsert_prices(settings.market_data_provider, confirmed_prices)
        logger.info(
            "Market refresh completed: symbol=%s expected=%s actual=%s rows=%s fetch_ms=%.0f save_ms=%.0f",
            symbol, confirmed_as_of, max(p.date for p in confirmed_prices), len(confirmed_prices),
            (fetched_at - started) * 1000, (perf_counter() - fetched_at) * 1000,
        )
        return confirmed_prices
