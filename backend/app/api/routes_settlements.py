from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.api.deps import CurrentOwnerDep, ensure_config_owner
from app.db.session import get_session
from app.domain.models import TradeSettlement
from app.dto.settlements import SettlementDraftDto, StrictDto
from app.services.order_snapshot_service import OrderSnapshotService
from app.services.settlement_service import SettlementService, state_of

router = APIRouter(prefix="/api/strategy-configs/{config_id}", tags=["settlements"])
SessionDep = Annotated[Session, Depends(get_session)]


class SnapshotRequest(StrictDto):
    sizing_policy: Literal["fixed_quantity", "full_allocation"] = "fixed_quantity"


class DraftUpdate(StrictDto):
    expected_revision: int
    draft: SettlementDraftDto


class ConfirmRequest(StrictDto):
    preview_hash: str = Field(min_length=64, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=100)


def run(action, session):
    try:
        return action()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(422, str(exc)) from exc
    except (IntegrityError, OperationalError) as exc:
        session.rollback()
        raise HTTPException(409, "동시 변경 또는 중복 요청입니다. 다시 확인해 주세요.") from exc


def authorize_record(config_id, settlement_id, owner, session):
    ensure_config_owner(config_id, owner, session)
    record = session.get(TradeSettlement, settlement_id)
    if record is None or record.config_id != config_id:
        raise HTTPException(404, "정산 내역을 찾을 수 없습니다.")
    return record


def record_view(record):
    return dict(id=record.id, trade_date=record.trade_date, snapshot_id=record.snapshot_id,
                status=record.status, revision=record.revision, draft=record.draft_json,
                result=record.result_json.get("response") if record.result_json else None)


@router.post("/order-snapshots")
def create_snapshot(config_id: int, request: SnapshotRequest, session: SessionDep, owner: CurrentOwnerDep):
    ensure_config_owner(config_id, owner, session)
    return run(lambda: state_of(OrderSnapshotService(session).create(config_id, request.sizing_policy)), session)


@router.get("/order-snapshots")
def list_snapshots(config_id: int, session: SessionDep, owner: CurrentOwnerDep, trade_date: date | None = None):
    ensure_config_owner(config_id, owner, session)
    return [state_of(s) for s in OrderSnapshotService(session).list(config_id, trade_date)]


@router.get("/settlement-context")
def get_context(config_id: int, trade_date: date, session: SessionDep, owner: CurrentOwnerDep,
                snapshot_id: int | None = None):
    ensure_config_owner(config_id, owner, session)
    ctx = run(lambda: SettlementService(session).context(config_id,
              SettlementDraftDto(trade_date=trade_date, snapshot_id=snapshot_id)), session)
    return jsonable_encoder(dict(sources=list(ctx.sources.values()), close=ctx.close,
                                  positions=list(ctx.positions.values())),
                             custom_encoder={Decimal: str})


@router.get("/settlements")
def list_settlements(config_id: int, session: SessionDep, owner: CurrentOwnerDep, trade_date: date | None = None):
    ensure_config_owner(config_id, owner, session)
    query = select(TradeSettlement).where(TradeSettlement.config_id == config_id)
    if trade_date:
        query = query.where(TradeSettlement.trade_date == trade_date)
    return [record_view(s) for s in session.scalars(query.order_by(TradeSettlement.id.desc()))]


@router.post("/settlements")
def create_draft(config_id: int, request: SettlementDraftDto, session: SessionDep, owner: CurrentOwnerDep):
    ensure_config_owner(config_id, owner, session)
    return run(lambda: record_view(SettlementService(session).save_draft(config_id, request)), session)


@router.put("/settlements/{settlement_id}/draft")
def update_draft(config_id: int, settlement_id: int, request: DraftUpdate, session: SessionDep, owner: CurrentOwnerDep):
    authorize_record(config_id, settlement_id, owner, session)
    return run(lambda: record_view(SettlementService(session).save_draft(
        config_id, request.draft, request.expected_revision, settlement_id)), session)


@router.post("/settlements/{settlement_id}/preview")
def preview(config_id: int, settlement_id: int, session: SessionDep, owner: CurrentOwnerDep):
    authorize_record(config_id, settlement_id, owner, session)
    return run(lambda: SettlementService(session).preview(settlement_id), session)


@router.post("/settlements/{settlement_id}/confirm")
def confirm(config_id: int, settlement_id: int, request: ConfirmRequest, session: SessionDep, owner: CurrentOwnerDep):
    authorize_record(config_id, settlement_id, owner, session)
    return run(lambda: SettlementService(session).confirm(
        settlement_id, request.preview_hash, request.idempotency_key), session)


@router.post("/settlements/{settlement_id}/cancel")
def cancel(config_id: int, settlement_id: int, session: SessionDep, owner: CurrentOwnerDep):
    authorize_record(config_id, settlement_id, owner, session)
    return run(lambda: SettlementService(session).cancel(settlement_id), session)
