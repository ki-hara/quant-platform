from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domain.enums import ModeConfirmationSource, StrategyMode


class ConfirmedModeUpdateDto(BaseModel):
    action: Literal["set", "apply_recommendation"]
    mode: StrategyMode | None = None


class ModeRecommendationDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    confirmed_mode: StrategyMode
    confirmed_source: ModeConfirmationSource
    recommended_mode: StrategyMode | None = None
    differs: bool
    effective_week: date | None = None
    data_as_of: date | None = None
    previous_rsi: Decimal | None = None
    current_rsi: Decimal | None = None
    rule_code: str | None = None


class LocPlanDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    limit_price: Decimal
    allocation: Decimal
    quantity: int
    estimated_fee: Decimal
    required_cash: Decimal
    available: Decimal
    blocking_reason: str | None
    orders: list["LocOrderDto"] = []


class LocOrderDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step: int
    limit_price: Decimal
    quantity: int
    cumulative_quantity: int


class DailyPlanDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan_date: date
    market_data_as_of: date | None
    symbol: str
    confirmed_mode: StrategyMode
    confirmed_source: ModeConfirmationSource
    recommended_mode: StrategyMode | None
    differs: bool
    effective_week: date | None
    data_as_of: date | None
    previous_rsi: Decimal | None
    current_rsi: Decimal | None
    rule_code: str | None
    previous_close: Decimal | None
    mode_buy_threshold_percent: Decimal | None
    capital: Decimal | None
    cash: Decimal | None
    mode_split_count: int | None
    open_position_count: int
    buy_available: bool
    LOC: LocPlanDto


class ChartCandleDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class ChartLineDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    value: Decimal
    as_of: date | None = None


class TradeMarkerDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    kind: Literal["buy", "sell"]
    price: Decimal
    quantity: Decimal
    source: str
    sell_reason: str | None = None


class RsiPointDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    value: Decimal


class RsiSeriesDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    guides: list[Decimal]
    points: list[RsiPointDto]


class ModeMarkerDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    mode: StrategyMode
    rule_code: str | None = None


class ChartResponseDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    candles: list[ChartCandleDto]
    LOC: ChartLineDto
    trade_markers: list[TradeMarkerDto]
    rsi: RsiSeriesDto
    mode_markers: list[ModeMarkerDto]


class MarketRefreshResponseDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    confirmed_mode: StrategyMode
    confirmed_source: ModeConfirmationSource
    recommended_mode: StrategyMode | None = None
    differs: bool
    investment_data_as_of: date | None = None
    rsi_data_as_of: date | None = None
