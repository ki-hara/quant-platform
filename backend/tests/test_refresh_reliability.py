from datetime import date, timedelta
from decimal import Decimal

from app.core.errors import MarketDataError
from app.dto.market_data import OhlcvDto
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.services.market_refresh_service import MarketRefreshService
from tests.test_chart_service import create_session, create_config


def quote(symbol, day, value='100', adjusted=True):
    return OhlcvDto(symbol=symbol, date=day, open=Decimal(value), high=Decimal(value),
                    low=Decimal(value), close=Decimal(value), volume=1, adjusted=adjusted)


def test_initial_range_failure_still_attempts_confirmed_day():
    day = date(2026, 9, 24)
    class Provider:
        def get_ohlcv(self, symbol, start, end):
            if start != day:
                raise MarketDataError('timeout', 'timeout')
            return [quote(symbol, day)]
    with create_session() as session:
        result = MarketRefreshService(session, Provider())._refresh_symbol('SOXL', day)
        assert result[0].date == day


def test_incremental_refresh_and_explicit_history():
    day = date(2026, 9, 24)
    calls = []
    class Provider:
        def get_ohlcv(self, symbol, start, end):
            calls.append(start)
            return [quote(symbol, day)]
    with create_session() as session:
        repo = MarketPriceRepository(session)
        repo.upsert_prices('finance_data_reader', [quote('SOXL', day-timedelta(days=i)) for i in range(1, 251)])
        service = MarketRefreshService(session, Provider())
        service._refresh_symbol('SOXL', day)
        service._refresh_symbol('SOXL', day, full_history=True)
    assert calls == [day-timedelta(days=8), day-timedelta(days=400)]


def test_rsi_failure_does_not_discard_successful_investment_refresh():
    day = date(2026, 9, 24)
    class Provider:
        def get_ohlcv(self, symbol, start, end):
            if symbol == 'QQQ':
                raise MarketDataError('timeout', 'timeout')
            return [quote(symbol, day)]
    with create_session() as session:
        config = create_config(session)
        result = MarketRefreshService(session, Provider()).refresh(config.id, today=day)
        assert result.investment_data_as_of == day
        assert result.rsi_data_as_of is None
        assert result.recommended_mode is None
        assert result.warnings


def test_shared_quote_selection_prefers_primary_and_retains_fallback():
    day = date(2026, 9, 24)
    with create_session() as session:
        repo = MarketPriceRepository(session)
        repo.upsert_prices('finance_data_reader', [quote('SOXL', day, '100', False), quote('SOXL', day, '101'), quote('SOXL', day-timedelta(days=1), '99', False)])
        rows = repo.list_prices('finance_data_reader', 'SOXL', day-timedelta(days=1), day)
        assert [p.close for p in rows] == [Decimal('99'), Decimal('101')]
        assert repo.latest_price_on_or_before('finance_data_reader', 'SOXL', day).close == Decimal('101')
