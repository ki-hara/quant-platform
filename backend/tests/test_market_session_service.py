from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.services.market_session_service import current_market_date, latest_confirmed_market_date


def test_us_symbol_before_cutoff_uses_previous_market_date() -> None:
    now = datetime(2026, 6, 26, 1, 0, tzinfo=ZoneInfo("Asia/Seoul"))

    assert latest_confirmed_market_date("SOXL", now) == date(2026, 6, 24)


def test_us_symbol_after_cutoff_uses_current_us_market_date() -> None:
    now = datetime(2026, 6, 26, 5, 40, tzinfo=ZoneInfo("Asia/Seoul"))

    assert latest_confirmed_market_date("SOXL", now) == date(2026, 6, 25)


def test_korean_symbol_before_cutoff_uses_previous_date() -> None:
    now = datetime(2026, 6, 26, 15, 20, tzinfo=ZoneInfo("Asia/Seoul"))

    assert latest_confirmed_market_date("005930.KS", now) == date(2026, 6, 25)


def test_korean_symbol_after_cutoff_uses_today() -> None:
    now = datetime(2026, 6, 26, 15, 50, tzinfo=ZoneInfo("Asia/Seoul"))

    assert latest_confirmed_market_date("005930.KS", now) == date(2026, 6, 26)


def test_alphanumeric_korean_symbol_uses_korean_market_date() -> None:
    now = datetime(2026, 6, 26, 15, 50, tzinfo=ZoneInfo("Asia/Seoul"))

    assert latest_confirmed_market_date("0193T0", now) == date(2026, 6, 26)
    assert current_market_date("0193T0", now) == date(2026, 6, 26)


def test_us_symbol_current_market_date_uses_new_york_date() -> None:
    now = datetime(2026, 6, 27, 2, 0, tzinfo=ZoneInfo("Asia/Seoul"))

    assert current_market_date("SOXL", now) == date(2026, 6, 26)
