from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from tests.test_chart_service import create_session, create_config
from app.api.routes_settlements import authorize_record
from app.domain.models import TradeSettlement
from datetime import date


def test_record_scope_and_owner_are_checked():
    with create_session() as session:
        config = create_config(session)
        record = TradeSettlement(config_id=config.id, trade_date=date(2026, 9, 24), draft_json={})
        session.add(record)
        session.commit()
        assert authorize_record(config.id, record.id, SimpleNamespace(id="default"), session).id == record.id
        with pytest.raises(HTTPException):
            authorize_record(config.id, record.id, SimpleNamespace(id="other"), session)
        with pytest.raises(HTTPException):
            authorize_record(config.id + 1, record.id, SimpleNamespace(id="default"), session)
