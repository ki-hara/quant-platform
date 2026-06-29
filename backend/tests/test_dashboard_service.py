from datetime import date
from types import SimpleNamespace

from app.services.dashboard_service import _trading_days_held


def test_trading_days_held_falls_back_to_weekdays_when_market_data_is_stale() -> None:
    prices = [SimpleNamespace(date=date(2026, 6, 25))]

    assert _trading_days_held(prices, date(2026, 6, 26), date(2026, 6, 29)) == 1
