from datetime import date, timedelta

from app.services.market_session_service import is_korean_symbol


def add_exchange_trading_days(symbol: str, start_date: date, trading_days: int) -> date:
    current = start_date
    remaining = trading_days
    while remaining > 0:
        current += timedelta(days=1)
        if is_exchange_trading_day(symbol, current):
            remaining -= 1
    return current


def previous_exchange_trading_day(symbol: str, value: date) -> date:
    current = value - timedelta(days=1)
    while not is_exchange_trading_day(symbol, current):
        current -= timedelta(days=1)
    return current


def count_exchange_trading_days(symbol: str, start_date: date, end_date: date) -> int:
    if end_date <= start_date:
        return 0
    current = start_date
    count = 0
    while current < end_date:
        current += timedelta(days=1)
        if is_exchange_trading_day(symbol, current):
            count += 1
    return count


def is_exchange_trading_day(symbol: str, value: date) -> bool:
    if value.weekday() >= 5:
        return False
    holidays = _krx_holidays(value.year) if is_korean_symbol(symbol) else _us_market_holidays(value.year)
    return value not in holidays


def _us_market_holidays(year: int) -> set[date]:
    return {
        _observed(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _good_friday(year),
        _last_weekday(year, 5, 0),
        _observed(date(year, 6, 19)),
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed(date(year, 12, 25)),
    }


def _krx_holidays(year: int) -> set[date]:
    holidays = {
        date(year, 1, 1),
        date(year, 3, 1),
        date(year, 5, 5),
        date(year, 6, 6),
        date(year, 8, 15),
        date(year, 10, 3),
        date(year, 10, 9),
        date(year, 12, 25),
    }
    holidays |= _KRX_LUNAR_AND_SPECIAL_HOLIDAYS.get(year, set())
    return {_observed(day) for day in holidays}


_KRX_LUNAR_AND_SPECIAL_HOLIDAYS: dict[int, set[date]] = {
    2026: {
        date(2026, 2, 16),
        date(2026, 2, 17),
        date(2026, 2, 18),
        date(2026, 5, 24),
        date(2026, 9, 24),
        date(2026, 9, 25),
        date(2026, 9, 26),
    },
    2027: {
        date(2027, 2, 6),
        date(2027, 2, 7),
        date(2027, 2, 8),
        date(2027, 5, 13),
        date(2027, 9, 14),
        date(2027, 9, 15),
        date(2027, 9, 16),
    },
}


def _observed(value: date) -> date:
    if value.weekday() == 5:
        return value - timedelta(days=1)
    if value.weekday() == 6:
        return value + timedelta(days=1)
    return value


def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> date:
    current = date(year, month, 1)
    while current.weekday() != weekday:
        current += timedelta(days=1)
    return current + timedelta(days=7 * (nth - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    current = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    while current.weekday() != weekday:
        current -= timedelta(days=1)
    return current


def _good_friday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day) - timedelta(days=2)
