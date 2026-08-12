from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo


NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class RegularSessionOpen:
    symbol: str
    session_date: date
    price: Decimal
    high: Decimal | None
    low: Decimal | None
    bar_time: datetime
    source: str


@dataclass(frozen=True)
class RegularOpenLookup:
    quote: RegularSessionOpen | None
    failure_reason: str | None = None


def regular_session_started(session_date: date, observed_at: datetime) -> bool:
    aware = observed_at.replace(tzinfo=UTC) if observed_at.tzinfo is None else observed_at
    return aware.astimezone(NEW_YORK) >= datetime.combine(
        session_date, time(9, 30), NEW_YORK
    )


def parse_price(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        parsed = Decimal(str(value).replace("$", "").replace(",", ""))
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def validate_open_ohlc(
    open_price: Decimal | None,
    high: Decimal | None,
    low: Decimal | None,
) -> str | None:
    if open_price is None:
        return "opening_bar_values_missing"
    if open_price <= 0:
        return "opening_bar_values_invalid"
    if high is not None and (high <= 0 or open_price > high):
        return "opening_bar_ohlc_invalid"
    if low is not None and (low <= 0 or low > open_price):
        return "opening_bar_ohlc_invalid"
    return None


def is_current_regular_quote(bar_time: datetime, session_date: date) -> bool:
    aware = bar_time.replace(tzinfo=UTC) if bar_time.tzinfo is None else bar_time
    local = aware.astimezone(NEW_YORK)
    return local.date() == session_date and local.time() >= time(9, 30)
