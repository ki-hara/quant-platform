from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.domain.enums import StrategyMode, TradeSide, TradeSource
from app.dto.dashboard import PositionDto


class TradeResponseDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    strategy_config_id: int
    date: date
    side: str
    quantity: Decimal
    limit_price: Decimal | None = None
    price: Decimal
    fee: Decimal
    realized_pnl: Decimal
    sell_reason: str | None
    source: str
    created_at: datetime
    updated_at: datetime


class SignalExecutionRequestDto(BaseModel):
    side: TradeSide
    trade_date: date
    quantity: Decimal
    limit_price: Decimal | None = None
    price: Decimal
    fee: Decimal
    source: TradeSource = TradeSource.SIGNAL_EXECUTION
    mode: StrategyMode = StrategyMode.SAFE
    position_id: int | None = None
    sell_reason: str | None = None


class SignalExecutionResponseDto(BaseModel):
    trade: TradeResponseDto
    cash: Decimal
    realized_pnl: Decimal


class ManualTradeRequestDto(BaseModel):
    config_id: int
    trade_date: date
    side: TradeSide
    quantity: Decimal
    limit_price: Decimal | None = None
    price: Decimal
    fee: Decimal
    sell_reason: str | None = None
    source: TradeSource = TradeSource.MANUAL
    mode: StrategyMode = StrategyMode.SAFE
    position_id: int | None = None


class ManualTradeResponseDto(BaseModel):
    trade: TradeResponseDto
    cash: Decimal
    realized_pnl: Decimal


class PositionsResponseDto(BaseModel):
    positions: list[PositionDto]
