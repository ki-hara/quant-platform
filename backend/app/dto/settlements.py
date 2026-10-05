from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=6, allow_inf_nan=False)]
Price = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=6, allow_inf_nan=False)]
Quantity = Annotated[int, Field(gt=0, le=100000000)]


class StrictDto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FillDto(StrictDto):
    id: str = Field(min_length=1, max_length=100)
    side: Literal["buy", "sell"]
    quantity: Quantity
    price: Price
    fee: Money


class AllocationDto(StrictDto):
    source_id: str
    fill_id: str | None = None
    side: Literal["buy", "sell"]
    quantity: Quantity
    kind: Literal["actual", "offset"]
    position_id: int | None = None
    change_reason: str = Field(default="", max_length=500)


class ManualBuySettingsDto(StrictDto):
    mode: Literal["safe", "aggressive"]
    sell_threshold_percent: Money
    max_holding_days: int = Field(ge=1, le=1000)


class SettlementDraftDto(StrictDto):
    snapshot_id: int | None = None
    trade_date: date
    fills: list[FillDto] = Field(default_factory=list, max_length=200)
    allocations: list[AllocationDto] = Field(default_factory=list, max_length=500)
    manual_buy_settings: ManualBuySettingsDto | None = None


class PreviewRowDto(StrictDto):
    source_id: str
    position_id: int | None
    side: Literal["buy", "sell"]
    quantity: int
    price: Decimal
    fee: Decimal
    kind: str
    fill_id: str | None
    realized_pnl: Decimal = Decimal("0")


class SettlementPreviewDto(StrictDto):
    rows: list[PreviewRowDto] = Field(default_factory=list)
    blocking_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    cash_delta: Decimal = Decimal("0")
    total_fee: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    preview_hash: str = ""


class QuickSelectionDto(StrictDto):
    position_id: int = Field(gt=0)
    quantity: Quantity
    price: Price
    fee: Money | None = None


class QuickSettlementDto(StrictDto):
    trade_date: date
    state_hash: str = Field(min_length=64, max_length=64)
    selections: list[QuickSelectionDto] = Field(min_length=1, max_length=200)
    netting: bool = True
