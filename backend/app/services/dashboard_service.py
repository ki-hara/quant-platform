from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.enums import PositionStatus, TradeSide
from app.domain.models import LivePortfolio, MarketPrice, PortfolioAdjustment, Position, StrategyConfig
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.infrastructure.repositories.portfolios import PortfolioRepository, PositionRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.infrastructure.repositories.trades import TradeRepository
from app.services.exchange_calendar_service import add_exchange_trading_days, count_exchange_trading_days
from app.services.fear_greed_service import FearGreedService
from app.services.market_session_service import current_market_date
from app.services.trend_filter_service import TrendFilterService
from app.strategy_engine.context import StrategyContext, StrategyPosition
from app.strategy_engine.loc import MONEY_QUANT
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
    capital_update: dict | None = None
    market_sentiment: object | None = None
    trend_filter: object | None = None


class DashboardService:
    def __init__(self, session: Session, market_data_provider: str | None = None) -> None:
        self.session = session
        self.configs = StrategyConfigRepository(session)
        self.portfolios = PortfolioRepository(session)
        self.positions = PositionRepository(session)
        self.market_prices = MarketPriceRepository(session)
        self.trades = TradeRepository(session)
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
        capital_update = None
        if portfolio is not None:
            capital_update = self._auto_apply_capital_update(config, portfolio, latest_prices)
            portfolio = self.portfolios.get_by_config(config_id) or portfolio

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
            capital_update=capital_update,
            market_sentiment=FearGreedService().get_current(),
            trend_filter=TrendFilterService(self.market_prices, self.market_data_provider).get_summary(
                config.symbol,
                config.settings_json,
                date.today(),
            ),
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

    def _auto_apply_capital_update(
        self,
        config: StrategyConfig,
        portfolio: LivePortfolio,
        prices: list[MarketPrice],
    ) -> dict | None:
        interval = _capital_update_interval(config.settings_json)
        if interval <= 0:
            return None

        trading_dates = sorted({price.date for price in prices})
        market_today = current_market_date(config.symbol)
        latest_date = trading_dates[-1] if trading_dates else market_today
        last_update = self._last_strategy_capital_update(config.id)
        all_trades = self.trades.list_by_strategy_config(config.id)
        first_trade = all_trades[0] if all_trades else None
        if last_update is None and first_trade is None:
            return _capital_update_status(
                status="waiting",
                interval=interval,
                elapsed=0,
                last_update_date=None,
                next_update_date=None,
                period_start_date=None,
                period_end_date=None,
                realized_pnl=Decimal("0"),
                capital_delta=Decimal("0"),
                projected_capital=portfolio.capital,
                message="거래 기록 없음",
            )

        basis_date = last_update.date if last_update is not None else first_trade.date
        period_start_date = basis_date
        period_end_date = add_exchange_trading_days(config.symbol, basis_date, interval)
        elapsed = min(
            count_exchange_trading_days(config.symbol, basis_date, market_today),
            interval,
        )
        if market_today < period_end_date:
            return _capital_update_status(
                status="waiting",
                interval=interval,
                elapsed=elapsed,
                last_update_date=last_update.date if last_update else None,
                next_update_date=period_end_date,
                period_start_date=period_start_date,
                period_end_date=period_end_date,
                realized_pnl=self._period_realized_pnl(config.id, period_start_date, latest_date, include_start=last_update is None),
                capital_delta=Decimal("0"),
                projected_capital=portfolio.capital,
                message="갱신 대기",
            )

        realized_pnl = self._period_realized_pnl(
            config.id,
            period_start_date,
            period_end_date,
            include_start=last_update is None,
        )
        capital_delta = _capital_delta(config.settings_json, realized_pnl)
        if realized_pnl == 0:
            return _capital_update_status(
                status="waiting",
                interval=interval,
                elapsed=elapsed,
                last_update_date=last_update.date if last_update else None,
                next_update_date=period_end_date,
                period_start_date=period_start_date,
                period_end_date=period_end_date,
                realized_pnl=realized_pnl,
                capital_delta=Decimal("0"),
                projected_capital=portfolio.capital,
                message="갱신 대상 실현손익 없음",
            )

        existing = self._strategy_capital_update_for_period(config.id, period_start_date, period_end_date)
        if existing is not None:
            return _capital_update_status(
                status="applied",
                interval=interval,
                elapsed=interval,
                last_update_date=existing.date,
                next_update_date=None,
                period_start_date=period_start_date,
                period_end_date=period_end_date,
                realized_pnl=realized_pnl,
                capital_delta=existing.capital_delta,
                projected_capital=portfolio.capital,
                applied=True,
                message="이미 갱신됨",
            )

        portfolio.capital = (portfolio.capital + capital_delta).quantize(MONEY_QUANT)
        adjustment = PortfolioAdjustment(
            strategy_config_id=config.id,
            date=period_end_date,
            cash_delta=Decimal("0").quantize(MONEY_QUANT),
            capital_delta=capital_delta.quantize(MONEY_QUANT),
            memo=(
                f"전략 주기 자동 갱신 / 실현손익 {realized_pnl.quantize(MONEY_QUANT)} / "
                f"기간 {period_start_date.isoformat()}~{period_end_date.isoformat()}"
            ),
            source="strategy_capital_update",
            period_start_date=period_start_date,
            period_end_date=period_end_date,
        )
        self.session.add(adjustment)
        self.session.add(portfolio)
        self.session.commit()
        return _capital_update_status(
            status="applied",
            interval=interval,
            elapsed=interval,
            last_update_date=period_end_date,
            next_update_date=None,
            period_start_date=period_start_date,
            period_end_date=period_end_date,
            realized_pnl=realized_pnl,
            capital_delta=capital_delta,
            projected_capital=portfolio.capital,
            applied=True,
            message="자동 갱신됨",
        )

    def _last_strategy_capital_update(self, config_id: int) -> PortfolioAdjustment | None:
        adjustments = [
            adjustment
            for adjustment in self.session.query(PortfolioAdjustment)
            .filter(PortfolioAdjustment.strategy_config_id == config_id)
            .filter(PortfolioAdjustment.source == "strategy_capital_update")
            .order_by(PortfolioAdjustment.date.desc(), PortfolioAdjustment.id.desc())
            .limit(1)
        ]
        return adjustments[0] if adjustments else None

    def _strategy_capital_update_for_period(
        self,
        config_id: int,
        period_start_date: date,
        period_end_date: date,
    ) -> PortfolioAdjustment | None:
        return (
            self.session.query(PortfolioAdjustment)
            .filter(PortfolioAdjustment.strategy_config_id == config_id)
            .filter(PortfolioAdjustment.source == "strategy_capital_update")
            .filter(PortfolioAdjustment.period_start_date == period_start_date)
            .filter(PortfolioAdjustment.period_end_date == period_end_date)
            .one_or_none()
        )

    def _period_realized_pnl(
        self,
        config_id: int,
        start_date: date,
        end_date: date,
        include_start: bool,
    ) -> Decimal:
        total = Decimal("0")
        for trade in self.trades.list_in_range(config_id, start_date, end_date):
            if trade.side != TradeSide.SELL:
                continue
            if not include_start and trade.date <= start_date:
                continue
            total += trade.realized_pnl
        return total.quantize(MONEY_QUANT)


def _sell_urgency(reason: str | None, days_to_deadline: int) -> str:
    if reason == "max_holding_period":
        return "expired"
    if reason == "profit_target":
        return "profit_target"
    if days_to_deadline <= 2:
        return "near_deadline"
    return "normal"


def _capital_update_interval(settings: dict) -> int:
    capital_update = settings.get("capital_update") if isinstance(settings, dict) else None
    if isinstance(capital_update, dict):
        value = capital_update.get("interval")
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    return 0


def _capital_delta(settings: dict, realized_pnl: Decimal) -> Decimal:
    if realized_pnl >= 0:
        rate = Decimal(str(settings.get("profit_compounding_rate", "0"))) / Decimal("100")
        return (realized_pnl * rate).quantize(MONEY_QUANT)
    rate = Decimal(str(settings.get("loss_compounding_rate", "0"))) / Decimal("100")
    return (realized_pnl * rate).quantize(MONEY_QUANT)


def _capital_update_status(
    status: str,
    interval: int,
    elapsed: int,
    last_update_date: date | None,
    next_update_date: date | None,
    period_start_date: date | None,
    period_end_date: date | None,
    realized_pnl: Decimal,
    capital_delta: Decimal,
    projected_capital: Decimal | None,
    applied: bool = False,
    message: str | None = None,
) -> dict:
    return {
        "status": status,
        "interval": interval,
        "elapsed_trading_days": elapsed,
        "last_update_date": last_update_date,
        "next_update_date": next_update_date,
        "period_start_date": period_start_date,
        "period_end_date": period_end_date,
        "realized_pnl": realized_pnl.quantize(MONEY_QUANT),
        "capital_delta": capital_delta.quantize(MONEY_QUANT),
        "projected_capital": projected_capital.quantize(MONEY_QUANT) if projected_capital is not None else None,
        "applied": applied,
        "message": message,
    }


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
