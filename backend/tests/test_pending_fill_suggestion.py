from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

from app.api import routes_trades as routes
from app.dto.dashboard import PositionDto
from app.domain.models import Owner
from tests.test_chart_service import create_session, create_config


def test_suggestion_uses_exact_confirmed_day_without_mutating_position(monkeypatch):
    rows = [PositionDto(id=i, strategy_config_id=1, buy_date=date(2026, 9, day),
                        buy_price=Decimal('100'), buy_fee=0, quantity=1, mode='safe',
                        status=status)
            for i, day, status in [(1, 22, 'pending'), (2, 23, 'pending'), (3, 22, 'open')]]
    monkeypatch.setattr(routes, 'latest_confirmed_market_date', lambda symbol: date(2026, 9, 22))
    monkeypatch.setattr(routes, 'PositionRepository', lambda session: SimpleNamespace(list_open=lambda id: rows))
    prices = Mock(return_value=[SimpleNamespace(date=date(2026, 9, 22), close=Decimal('98'), adjusted=True)])
    monkeypatch.setattr(routes, 'MarketPriceRepository', lambda session: SimpleNamespace(list_prices=prices))
    with create_session() as session:
        config = create_config(session)
        result = routes.list_positions(config.id, session, session.get(Owner, 'default'))
    assert [r.suggested_fill_price for r in result] == [Decimal('98'), None, None]
    assert all(r.buy_price == 100 for r in rows)
    assert prices.call_args.args[-1] == date(2026, 9, 22)
