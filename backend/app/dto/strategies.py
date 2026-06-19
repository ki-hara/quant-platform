from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrategyDto(BaseModel):
    type: str
    name: str


class StrategySchemaDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    strategy_type: str
    schema_: dict[str, Any] = Field(alias="schema")


class StrategyConfigCreateDto(BaseModel):
    name: str
    strategy_type: str
    symbol: str
    initial_capital: Decimal
    fee_rate: Decimal
    slippage_rate: Decimal
    settings_json: dict[str, Any]


class StrategyConfigResponseDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: str
    name: str
    strategy_type: str
    symbol: str
    initial_capital: Decimal
    fee_rate: Decimal
    slippage_rate: Decimal
    settings_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
