from sqlalchemy import select
from app.domain.models import TradeSettlement, OrderSnapshot, OrderSnapshotInvalidation
from app.core.errors import ValidationAppError


def guard_ledger_rebuild(session, config_id):
    active = session.scalar(select(TradeSettlement.id).where(
        TradeSettlement.config_id == config_id, TradeSettlement.status == "confirmed").limit(1))
    if active:
        raise ValidationAppError("settlement_ledger_locked",
                                 "확정 정산이 있어 개별 거래 삭제·체결 보정을 할 수 없습니다. 정산 취소를 먼저 확인해 주세요.")


def invalidate_order_snapshots(session, config_id):
    # Ledger rebuilding can reuse position IDs; keep the original snapshot immutable.
    for snapshot_id in session.scalars(select(OrderSnapshot.id).where(OrderSnapshot.config_id == config_id)):
        if session.get(OrderSnapshotInvalidation, snapshot_id) is None:
            session.add(OrderSnapshotInvalidation(snapshot_id=snapshot_id))
