from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.enums import PositionStatus
from app.domain.models import LivePortfolio, MarketPrice, Position, StrategyConfig
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.infrastructure.repositories.portfolios import PortfolioRepository, PositionRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.services.market_session_service import current_market_date
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
    def __init__(self, session: Session, market_data_provider: str | None = None) -> None:
        self.configs = StrategyConfigRepository(session)
        self.portfolios = PortfolioRepository(session)
        self.positions = PositionRepository(session)
        self.market_prices = MarketPriceRepository(session)
        self.market_data_provider = market_data_provider or settings.market_data_provider

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
        holding_basis_date = current_market_date(config.symbol)
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
                    holding_days=_trading_days_held(prices, position.buy_date, holding_basis_date),
                )
                for position in open_positions
            ],
            settings=config.settings_json,
            trading_day_index=len(prices) - 1,
        )
        strategy = registry.create(config.strategy_type)
        buy_signal = strategy.should_buy(context)
        sell_signals = []
        for position in open_positions:
            if position.status != PositionStatus.OPEN:
                continue
            holding_days = _trading_days_held(prices, position.buy_date, holding_basis_date)
            strategy_position = StrategyPosition(
                buy_date=position.buy_date,
                buy_price=position.buy_price,
                quantity=int(position.quantity),
                mode=position.mode,
                holding_days=holding_days,
            )
            signal = strategy.should_sell(context, strategy_position)
            mode_settings = config.settings_json[position.mode.value]
            max_holding_days = int(mode_settings["max_holding_days"])
            days_to_deadline = max_holding_days - holding_days
            sell_limit_price = (
                position.buy_price
                * (Decimal("1") + Decimal(str(mode_settings["sell_threshold_percent"])) / Decimal("100"))
            ).quantize(Decimal("0.000001"))
            sell_signals.append(
                {
                    "position_id": position.id,
                    "should_sell": signal.should_sell,
                    "reason": signal.reason,
                    "return_percent": signal.return_percent,
                    "sell_limit_price": sell_limit_price,
                    "holding_days": holding_days,
                    "max_holding_days": max_holding_days,
                    "days_to_deadline": days_to_deadline,
                    "urgency": _sell_urgency(signal.reason, days_to_deadline),
                }
            )
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


def _sell_urgency(reason: str | None, days_to_deadline: int) -> str:
    if reason == "max_holding_period":
        return "expired"
    if reason == "profit_target":
        return "profit_target"
    if days_to_deadline <= 2:
        return "near_deadline"
    return "normal"


def _trading_days_held(prices: list[MarketPrice], buy_date: date, basis_date: date) -> int:
    if basis_date <= buy_date:
        return 0
    available_dates = sorted({price.date for price in prices if buy_date < price.date <= basis_date})
    if not available_dates:
        return _weekday_count(buy_date, basis_date)
    latest_available_date = available_dates[-1]
    return len(available_dates) + _weekday_count(latest_available_date, basis_date)


def _weekday_count(start_exclusive: date, end_inclusive: date) -> int:
    count = 0
    current = start_exclusive + timedelta(days=1)
    while current <= end_inclusive:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count
