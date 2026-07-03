from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.dto.trading_plan import MarketRefreshResponseDto
from app.infrastructure.market_data.base import MarketDataProvider
from app.infrastructure.market_data.finance_data_reader_provider import FinanceDataReaderProvider
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
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

    def refresh(self, config_id: int, today: date) -> MarketRefreshResponseDto:
        config = self.configs.get(config_id)
        if config is None:
            raise ValueError(f"Strategy config not found: {config_id}")

        rsi_symbol = str(config.settings_json.get("mode_rsi_symbol", "QQQ"))
        start_date = today - timedelta(days=400)
        investment_prices = self.provider.get_ohlcv(config.symbol, start_date, today)
        self.market_prices.upsert_prices(settings.market_data_provider, investment_prices)
        rsi_prices = self.provider.get_ohlcv(rsi_symbol, start_date, today)
        self.market_prices.upsert_prices(settings.market_data_provider, rsi_prices)
        for symbol in trend_filter_symbols(config.settings_json, config.symbol):
            if symbol in {config.symbol, rsi_symbol}:
                continue
            trend_prices = self.provider.get_ohlcv(symbol, start_date, today)
            self.market_prices.upsert_prices(settings.market_data_provider, trend_prices)

        recommendation = ModeService(self.session).get_mode_recommendation(config_id, as_of=today)
        return MarketRefreshResponseDto(
            confirmed_mode=recommendation.confirmed_mode,
            confirmed_source=recommendation.confirmed_source,
            recommended_mode=recommendation.recommended_mode,
            differs=recommendation.differs,
            investment_data_as_of=max((price.date for price in investment_prices), default=None),
            rsi_data_as_of=max((price.date for price in rsi_prices), default=None),
        )
