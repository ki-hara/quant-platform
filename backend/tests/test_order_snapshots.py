from copy import deepcopy
from decimal import Decimal
import pytest

from tests.test_chart_service import create_session, create_config
from app.services.order_snapshot_service import OrderSnapshotService


def test_snapshots_are_immutable_and_do_not_create_positions():
    with create_session() as session:
        config = create_config(session)
        service = OrderSnapshotService(session)
        first = service.create(config.id)
        original = deepcopy(first.payload_json)
        changed = deepcopy(config.settings_json)
        changed['safe']['split_count'] = 9
        config.settings_json = changed
        session.commit()
        second = service.create(config.id)
        assert first.id != second.id
        assert first.payload_json == original
        assert second.payload_json['settings']['safe']['split_count'] == 9
        assert config.positions == []
        assert config.live_portfolio.cash == 1000


def test_ledger_rebuild_invalidates_snapshot_without_changing_original():
    from app.dto.settlements import SettlementDraftDto
    from app.services.settlement_service import SettlementService
    from app.services.manual_trade_service import ManualTradeService
    with create_session() as session:
        config = create_config(session)
        snapshot = OrderSnapshotService(session).create(config.id)
        original = deepcopy(snapshot.payload_json)
        ManualTradeService(session)._rebuild_live_ledger(config, config.live_portfolio)
        session.commit()
        assert snapshot.payload_json == original
        with pytest.raises(ValueError, match='재구성'):
            SettlementService(session).context(config.id, SettlementDraftDto(
                snapshot_id=snapshot.id, trade_date=snapshot.trade_date))


def test_snapshot_preserves_selected_cash_shortage_policy(monkeypatch):
    from app.services.daily_plan_service import DailyPlanService
    with create_session() as session:
        config = create_config(session)
        plan = DailyPlanService(session).get_daily_plan(config.id)
        plan.buy_available = False
        plan.cash = Decimal('250')
        plan.LOC.limit_price = Decimal('100')
        plan.LOC.quantity = 5
        plan.LOC.orders = []
        plan.LOC.blocking_reason = 'insufficient_cash'
        monkeypatch.setattr(DailyPlanService, 'get_daily_plan', lambda *a, **kw: plan)
        service = OrderSnapshotService(session)
        for policy, expected in [('defer', 0), ('available_cash', 2), ('external_funding', 5)]:
            snapshot = service.create(config.id, cash_shortage_policy=policy)
            assert sum(s['quantity'] for s in snapshot.payload_json['sources'] if s['side']=='buy') == expected
        assert config.live_portfolio.cash == 1000
