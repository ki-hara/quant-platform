from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.domain.enums import BacktestModePolicy, BacktestPositionSizingPolicy


class BacktestCreateDto(BaseModel):
    config_id: int
    start_date: date
    end_date: date
    mode_policy: BacktestModePolicy = BacktestModePolicy.FIXED_SAFE
    position_sizing_policy: BacktestPositionSizingPolicy = BacktestPositionSizingPolicy.FIXED_QUANTITY


class BacktestRunResponseDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: str
    strategy_config_snapshot_json: dict[str, Any]
    start_date: date
    end_date: date
    status: str
    error_message: str | None
    initial_capital: Decimal
    final_capital: Decimal
    total_return: Decimal
    max_drawdown: Decimal
    win_rate: Decimal
    total_trades: int
    created_at: datetime
    updated_at: datetime
