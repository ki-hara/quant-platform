import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


US_CUTOFF = time(16, 30)
KR_CUTOFF = time(15, 40)


def latest_confirmed_market_date(symbol: str, now: datetime | None = None) -> date:
    current = now or datetime.now(ZoneInfo("Asia/Seoul"))
    if _is_korean_symbol(symbol):
        local = current.astimezone(ZoneInfo("Asia/Seoul"))
        basis = local.date() if local.time() >= KR_CUTOFF else local.date() - timedelta(days=1)
    else:
        local = current.astimezone(ZoneInfo("America/New_York"))
        basis = local.date() if local.time() >= US_CUTOFF else local.date() - timedelta(days=1)
    return _previous_weekday(basis)


def current_market_date(symbol: str, now: datetime | None = None) -> date:
    current = now or datetime.now(ZoneInfo("Asia/Seoul"))
    zone = ZoneInfo("Asia/Seoul") if _is_korean_symbol(symbol) else ZoneInfo("America/New_York")
    return current.astimezone(zone).date()


def _is_korean_symbol(symbol: str) -> bool:
    normalized = symbol.strip().upper()
    compact = normalized.removeprefix("KRX:").removeprefix("KOSPI:").removeprefix("KOSDAQ:").removeprefix("A")
    return compact.endswith(".KS") or compact.endswith(".KQ") or bool(re.fullmatch(r"[0-9A-Z]{6}", compact))


def _previous_weekday(value: date) -> date:
    while value.weekday() >= 5:
        value -= timedelta(days=1)
    return value
