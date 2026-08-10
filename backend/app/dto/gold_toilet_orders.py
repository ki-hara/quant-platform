from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class GoldToiletAccountUpdateDto(BaseModel):
    capital: Decimal = Field(gt=0)
    cash: Decimal = Field(ge=0)


class GoldToiletAccountDto(GoldToiletAccountUpdateDto):
    updated_at: datetime
    model_config = {"from_attributes": True}


class GoldToiletOrderSheetUpdateDto(BaseModel):
    entry_percent: Decimal = Field(gt=-100)
    allocation_percent: Decimal = Field(gt=0, le=100)
    loc_percent: Decimal = Field(gt=-100)
    model_config = {"extra": "forbid"}


class GoldToiletManualOpenUpdateDto(BaseModel):
    market_open: Decimal = Field(gt=0)


class GoldToiletOrderSheetDto(BaseModel):
    order_date: date
    entry_percent: Decimal
    allocation_percent: Decimal
    loc_percent: Decimal
    provider_market_open: Decimal | None
    provider_open_observed_at: datetime | None
    provider_open_source: str | None
    provider_open_last_checked_at: datetime | None
    provider_open_failure_reason: str | None
    manual_market_open: Decimal | None
    manual_open_observed_at: datetime | None
    effective_market_open: Decimal | None
    effective_open_source: Literal["manual", "yahoo_1d_regular_session"] | None
    updated_at: datetime


class GoldToiletCalculationDto(BaseModel):
    breakout_buy_price: Decimal
    order_quantity: int
    loc_buy_price: Decimal
    allocation_amount: Decimal
    required_reservation_cash: Decimal
    cash_warning: bool
    model_config = {"from_attributes": True}


class GoldToiletOrderResponseDto(BaseModel):
    symbol: Literal["SOXL"] = "SOXL"
    account: GoldToiletAccountDto | None
    sheet: GoldToiletOrderSheetDto | None
    allocation_amount: Decimal | None
    calculation: GoldToiletCalculationDto | None
    open_status: Literal["waiting", "ready", "failed"]
    open_failure_reason: str | None = None
