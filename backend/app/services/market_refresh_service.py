from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.dto.trading_plan import MarketRefreshResponseDto
from app.infrastructure.market_data.base import MarketDataProvider
from app.infrastructure.market_data.finance_data_reader_provider import FinanceDataReaderProvider
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.services.market_session_service import latest_confirmed_market_date
from app.services.mode_service import ModeService
from app.services.trend_filter_service import trend_filter_symbols


def get_market_data_provider() -> MarketDataProvider:
    return FinanceDataReaderProvider()


class MarketRefreshService:
    def __init__(self, session: Session, provider: MarketDataProvider) -> None:
        self.session = session
        self.provider = provider
        self.configs = StrategyConfigRepository(session)
        self.market_prices = MarketPriceRepository(session)

    def refresh(self, config_id: int, today: date | None = None) -> MarketRefreshResponseDto:
        config = self.configs.get(config_id)
        if config is None:
            raise ValueError(f"Strategy config not found: {config_id}")

        rsi_symbol = str(config.settings_json.get("mode_rsi_symbol", "QQQ"))
        investment_as_of = today or latest_confirmed_market_date(config.symbol)
        rsi_as_of = today or latest_confirmed_market_date(rsi_symbol)
        investment_prices = self._refresh_symbol(config.symbol, investment_as_of)
        rsi_prices = self._refresh_symbol(rsi_symbol, rsi_as_of)
        for symbol in trend_filter_symbols(config.settings_json, config.symbol):
            if symbol not in {config.symbol, rsi_symbol}:
                self._refresh_symbol(symbol, today or latest_confirmed_market_date(symbol))

        recommendation = ModeService(self.session).get_mode_recommendation(config_id, as_of=rsi_as_of)
        return MarketRefreshResponseDto(
            confirmed_mode=recommendation.confirmed_mode,
            confirmed_source=recommendation.confirmed_source,
            recommended_mode=recommendation.recommended_mode,
            differs=recommendation.differs,
            investment_data_as_of=max((price.date for price in investment_prices), default=None),
            rsi_data_as_of=max((price.date for price in rsi_prices), default=None),
        )

    def _refresh_symbol(self, symbol: str, confirmed_as_of: date) -> list:
        start_date = confirmed_as_of - timedelta(days=400)
        prices = self.provider.get_ohlcv(symbol, start_date, confirmed_as_of + timedelta(days=1))
        confirmed_prices = [price for price in prices if price.date <= confirmed_as_of]
        self.market_prices.upsert_prices(settings.market_data_provider, confirmed_prices)
        return confirmed_prices
