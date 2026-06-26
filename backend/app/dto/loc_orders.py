from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.domain.enums import LocOrderStatus, StrategyMode


class LocOrderCreateDto(BaseModel):
    memo: str | None = None


class LocOrderFillDto(BaseModel):
    quantity: Decimal
    price: Decimal
    fee: Decimal = Decimal("0")
    memo: str | None = None


class LocOrderResponseDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    strategy_config_id: int
    order_date: date
    symbol: str
    limit_price: Decimal
    recommended_quantity: Decimal
    mode: StrategyMode
    status: LocOrderStatus
    trade_id: int | None
    memo: str | None
    created_at: datetime
    updated_at: datetime
