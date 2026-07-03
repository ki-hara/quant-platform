from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.dto.strategies import StrategyConfigResponseDto


class PortfolioDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    strategy_config_id: int
    capital: Decimal
    cash: Decimal
    realized_pnl: Decimal
    cumulative_fees: Decimal


class PositionDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    strategy_config_id: int
    buy_date: date
    limit_price: Decimal | None = None
    buy_price: Decimal
    buy_fee: Decimal
    quantity: Decimal
    mode: str
    status: str


class MarketPriceDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    adjusted: bool


class DashboardSignalResponseDto(BaseModel):
    available: bool
    should_buy: bool = False
    buy_reason: str | None = None
    sell_signals: list[dict] | None = None
    reason: str | None = None


class CapitalUpdateStatusDto(BaseModel):
    status: str
    interval: int
    elapsed_trading_days: int
    last_update_date: date | None
    next_update_date: date | None
    period_start_date: date | None
    period_end_date: date | None
    realized_pnl: Decimal
    capital_delta: Decimal
    projected_capital: Decimal | None
    applied: bool = False
    message: str | None = None


class MarketSentimentDto(BaseModel):
    score: int | None = None
    rating: str | None = None
    label: str
    as_of: date | None = None
    source: str
    available: bool = True


class TrendFilterSymbolDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    status: str
    label: str
    risk_label: str
    streak: int
    latest_cci: Decimal | None = None
    as_of: date | None = None
    zero_distance: Decimal | None = None


class TrendFilterDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbols: list[TrendFilterSymbolDto]
    summary: str


class DashboardResponseDto(BaseModel):
    config: StrategyConfigResponseDto
    portfolio: PortfolioDto | None
    open_positions: list[PositionDto]
    latest_price: MarketPriceDto | None
    total_asset: Decimal | None
    signals: DashboardSignalResponseDto
    capital_update: CapitalUpdateStatusDto | None = None
    market_sentiment: MarketSentimentDto | None = None
    trend_filter: TrendFilterDto | None = None
