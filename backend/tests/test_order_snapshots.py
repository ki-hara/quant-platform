from copy import deepcopy

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
