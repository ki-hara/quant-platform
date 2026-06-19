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


class DashboardResponseDto(BaseModel):
    config: StrategyConfigResponseDto
    portfolio: PortfolioDto | None
    open_positions: list[PositionDto]
    latest_price: MarketPriceDto | None
    total_asset: Decimal | None
    signals: DashboardSignalResponseDto
