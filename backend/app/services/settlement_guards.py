from sqlalchemy import select
from app.domain.models import TradeSettlement
from app.core.errors import ValidationAppError


def guard_ledger_rebuild(session, config_id):
    active = session.scalar(select(TradeSettlement.id).where(
        TradeSettlement.config_id == config_id, TradeSettlement.status == "confirmed").limit(1))
    if active:
        raise ValidationAppError("settlement_ledger_locked",
                                 "확정 정산이 있어 개별 거래 삭제·체결 보정을 할 수 없습니다. 정산 취소를 먼저 확인해 주세요.")
