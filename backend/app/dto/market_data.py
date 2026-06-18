from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class OhlcvDto(BaseModel):
    symbol: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    adjusted: bool = True
