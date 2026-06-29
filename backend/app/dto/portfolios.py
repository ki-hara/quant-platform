from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PortfolioAdjustmentCreateDto(BaseModel):
    date: date
    cash_delta: Decimal
    capital_delta: Decimal
    memo: str | None = None


class PortfolioAdjustmentResponseDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    strategy_config_id: int
    date: date
    cash_delta: Decimal
    capital_delta: Decimal
    memo: str | None
    source: str
    period_start_date: date | None
    period_end_date: date | None
    created_at: datetime
