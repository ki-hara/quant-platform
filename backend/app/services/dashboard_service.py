from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.models import LivePortfolio, MarketPrice, Position, StrategyConfig
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.infrastructure.repositories.portfolios import PortfolioRepository, PositionRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.strategy_engine.context import StrategyContext, StrategyPosition
from app.strategy_engine.registry import registry


@dataclass(frozen=True)
class DashboardSignalDto:
    available: bool
    should_buy: bool = False
    buy_reason: str | None = None
    sell_signals: list[dict] | None = None
    reason: str | None = None


@dataclass(frozen=True)
class DashboardDto:
    config: StrategyConfig
    portfolio: LivePortfolio | None
    open_positions: list[Position]
    latest_price: MarketPrice | None
    total_asset: Decimal | None
    signals: DashboardSignalDto


class DashboardService:
    def __init__(self, session: Session, market_data_provider: str = "finance-data-reader") -> None:
        self.configs = StrategyConfigRepository(session)
        self.portfolios = PortfolioRepository(session)
        self.positions = PositionRepository(session)
        self.market_prices = MarketPriceRepository(session)
        self.market_data_provider = market_data_provider

    def get_dashboard(self, config_id: int) -> DashboardDto:
        config = self._get_config(config_id)
        portfolio = self.portfolios.get_by_config(config_id)
        open_positions = self.positions.list_open(config_id)
        latest_prices = self.market_prices.list_prices(
            self.market_data_provider,
            config.symbol,
            date.min,
            date.today(),
        )
        latest_price = latest_prices[-1] if latest_prices else None

        total_asset = None
        if portfolio is not None and latest_price is not None:
            position_value = sum(
                (position.quantity * latest_price.close for position in open_positions),
                Decimal("0"),
            )
            total_asset = portfolio.cash + position_value

        signals = self._signals(config, portfolio, open_positions, latest_prices)
        return DashboardDto(
            config=config,
            portfolio=portfolio,
            open_positions=open_positions,
            latest_price=latest_price,
            total_asset=total_asset,
            signals=signals,
        )

    def _signals(
        self,
        config: StrategyConfig,
        portfolio: LivePortfolio | None,
        open_positions: list[Position],
        prices: list[MarketPrice],
    ) -> DashboardSignalDto:
        if portfolio is None:
            return DashboardSignalDto(available=False, reason="portfolio_unavailable")
        if len(prices) < 2:
            return DashboardSignalDto(available=False, reason="market_data_unavailable")

        current_price = prices[-1]
        previous_price = prices[-2]
        context = StrategyContext(
            current_date=current_price.date,
            previous_close=previous_price.close,
            current_close=current_price.close,
            capital=portfolio.capital,
            cash=portfolio.cash,
            open_positions=[
                StrategyPosition(
                    buy_date=position.buy_date,
                    buy_price=position.buy_price,
                    quantity=int(position.quantity),
                    mode=position.mode,
                )
                for position in open_positions
            ],
            settings=config.settings_json,
            trading_day_index=len(prices) - 1,
        )
        strategy = registry.create(config.strategy_type)
        buy_signal = strategy.should_buy(context)
        sell_signals = [
            {
                "position_id": position.id,
                "should_sell": signal.should_sell,
                "reason": signal.reason,
                "return_percent": signal.return_percent,
            }
            for position, signal in (
                (
                    position,
                    strategy.should_sell(
                        context,
                        StrategyPosition(
                            buy_date=position.buy_date,
                            buy_price=position.buy_price,
                            quantity=int(position.quantity),
                            mode=position.mode,
                        ),
                    ),
                )
                for position in open_positions
            )
        ]
        return DashboardSignalDto(
            available=True,
            should_buy=buy_signal.should_buy,
            buy_reason=buy_signal.reason,
            sell_signals=sell_signals,
        )

    def _get_config(self, config_id: int) -> StrategyConfig:
        config = self.configs.get(config_id)
        if config is None:
            raise ValueError(f"Strategy config not found: {config_id}")
        return config
