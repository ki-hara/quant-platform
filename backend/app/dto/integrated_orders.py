from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class IntegratedOrderPreferenceDto(BaseModel):
    strategy_config_id: int
    strategy_name: str
    strategy_type: str
    symbol: str
    included: bool


class IntegratedOrderPreferenceUpdateDto(BaseModel):
    included: bool


class IntegratedOrderSourceDto(BaseModel):
    strategy_config_id: int
    strategy_name: str
    strategy_type: str
    symbol: str
    side: Literal["buy", "sell"]
    limit_price: Decimal
    quantity: int
    tier: int | None = None
    radar_profile: str | None = None
    position_id: int | None = None


class IntegratedOrderDto(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    limit_price: Decimal
    quantity: int
    sources: list[IntegratedOrderSourceDto]


class IntegratedOrdersResponseDto(BaseModel):
    preferences: list[IntegratedOrderPreferenceDto]
    original_orders: list[IntegratedOrderDto]
    netted_orders: list[IntegratedOrderDto]
