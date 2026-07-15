from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from decimal import Decimal
from sqlalchemy.orm import Session

from app.api.deps import (
    CurrentOwnerDep,
    ensure_config_owner,
    ensure_position_owner,
    ensure_trade_owner,
)
from app.core.errors import NotFoundError, ValidationAppError
from app.db.session import get_session
from app.domain.enums import PositionStatus, StrategyMode, TradeSide, TradeSource
from app.domain.models import LocOrder
from app.dto.dashboard import PositionDto
from app.dto.trades import (
    ManualTradeRequestDto,
    ManualTradeResponseDto,
    PositionHistoryDto,
    SignalExecutionRequestDto,
    SignalExecutionResponseDto,
    TradeResponseDto,
)
from app.dto.loc_orders import LocOrderCreateDto, LocOrderFillDto, LocOrderResponseDto
from app.infrastructure.repositories.portfolios import PositionRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.infrastructure.repositories.trades import TradeRepository
from app.services.manual_trade_service import ManualTradeRequest, ManualTradeService
from app.services.position_exit_policy import build_position_exit_policy, sell_limit_price_for
from app.services.loc_order_service import LocOrderFillRequest, LocOrderService
from app.services.signal_execution_service import (
    SignalExecutionRequest,
    SignalExecutionService,
)


router = APIRouter(prefix="/api", tags=["trades"])


SessionDep = Annotated[Session, Depends(get_session)]


class PositionUpdateDto(BaseModel):
    quantity: Decimal | None = None
    buy_price: Decimal | None = None
    status: str | None = None


class BuyOrderPositionCreateDto(BaseModel):
    order_date: date
    quantity: Decimal
    limit_price: Decimal
    mode: StrategyMode


@router.get("/strategy-configs/{config_id}/positions", response_model=list[PositionDto])
def list_positions(config_id: int, session: SessionDep, owner: CurrentOwnerDep) -> list[object]:
    ensure_config_owner(config_id, owner, session)
    return PositionRepository(session).list_open(config_id)


@router.get("/positions/{config_id}", response_model=list[PositionDto])
def list_positions_by_config(config_id: int, session: SessionDep, owner: CurrentOwnerDep) -> list[object]:
    return list_positions(config_id, session, owner)


@router.post(
    "/strategy-configs/{config_id}/positions/buy-order",
    response_model=PositionDto,
    status_code=status.HTTP_201_CREATED,
)
def create_buy_order_position(
    config_id: int,
    request: BuyOrderPositionCreateDto,
    session: SessionDep,
    owner: CurrentOwnerDep,
) -> object:
    ensure_config_owner(config_id, owner, session)
    if request.quantity <= 0 or request.limit_price <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quantity and LOC price must be positive.")
    position = PositionRepository(session).create_pending(
        strategy_config_id=config_id,
        buy_date=request.order_date,
        limit_price=request.limit_price,
        quantity=request.quantity,
        mode=request.mode,
    )
    session.commit()
    return position


@router.put("/positions/{position_id}", response_model=PositionDto)
def update_position(
    position_id: int,
    request: PositionUpdateDto,
    session: SessionDep,
    owner: CurrentOwnerDep,
) -> object:
    repo = PositionRepository(session)
    position = ensure_position_owner(position_id, owner, session)
    config = StrategyConfigRepository(session).get(position.strategy_config_id)
    matching_trade = _matching_buy_trade(position, session)
    if request.status == "unfilled":
        if matching_trade is not None:
            TradeRepository(session).delete(matching_trade)
            if config is not None and config.live_portfolio is not None:
                ManualTradeService(session)._rebuild_live_ledger(config, config.live_portfolio)
        else:
            session.delete(position)
        session.commit()
        return position
    if request.status == "pending":
        session.commit()
        return position
    if request.quantity is not None:
        position.quantity = request.quantity
    if request.buy_price is not None:
        position.buy_price = request.buy_price
    if request.status == "open":
        position.status = PositionStatus.OPEN
    if position.status == PositionStatus.PENDING:
        saved = repo.save(position)
        session.commit()
        return saved
    if config is not None and position.status == PositionStatus.OPEN:
        if position.sell_threshold_percent is None or position.max_holding_days is None:
            exit_policy = build_position_exit_policy(config.settings_json, position.mode, position.buy_price)
            position.sell_threshold_percent = exit_policy.sell_threshold_percent
            position.sell_limit_price = exit_policy.sell_limit_price
            position.max_holding_days = exit_policy.max_holding_days
        elif request.buy_price is not None:
            position.sell_limit_price = sell_limit_price_for(
                position.buy_price,
                position.sell_threshold_percent,
            )

    fee = _estimate_fee(config, position.buy_price, position.quantity)
    position.buy_fee = fee
    created_trade = False
    if matching_trade is None:
        if config is None or config.live_portfolio is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Live portfolio not found.")
        trade_repo = TradeRepository(session)
        trade_repo.create(
            strategy_config_id=position.strategy_config_id,
            trade_date=position.buy_date,
            side=TradeSide.BUY,
            quantity=position.quantity,
            limit_price=position.limit_price,
            price=position.buy_price,
            fee=fee,
            realized_pnl=Decimal("0"),
            sell_reason=None,
            source=TradeSource.MANUAL,
        )
        config.live_portfolio.cash -= (position.buy_price * position.quantity) + fee
        config.live_portfolio.cumulative_fees += fee
        session.add(config.live_portfolio)
        created_trade = True
    else:
        matching_trade.quantity = position.quantity
        matching_trade.price = position.buy_price
        matching_trade.fee = fee
        session.add(matching_trade)
    saved = repo.save(position)
    if not created_trade and config is not None and config.live_portfolio is not None:
        ManualTradeService(session)._rebuild_live_ledger(config, config.live_portfolio)
    session.commit()
    return saved


def _matching_buy_trade(position, session: Session):
    for trade in TradeRepository(session).list_by_strategy_config(position.strategy_config_id):
        if (
            trade.side == TradeSide.BUY
            and trade.date == position.buy_date
            and trade.limit_price == position.limit_price
            and trade.price == position.buy_price
            and trade.quantity == position.quantity
        ):
            return trade
    return None


def _estimate_fee(config, price: Decimal, quantity: Decimal) -> Decimal:
    fee_rate = config.fee_rate if config is not None else Decimal("0")
    return (price * quantity * fee_rate / Decimal("100")).quantize(Decimal("0.000001"))


@router.get("/strategy-configs/{config_id}/trades", response_model=list[TradeResponseDto])
def list_trades(config_id: int, session: SessionDep, owner: CurrentOwnerDep) -> list[object]:
    ensure_config_owner(config_id, owner, session)
    return TradeRepository(session).list_by_strategy_config(config_id)


@router.get("/strategy-configs/{config_id}/position-history", response_model=list[PositionHistoryDto])
def list_position_history(config_id: int, session: SessionDep, owner: CurrentOwnerDep) -> list[object]:
    ensure_config_owner(config_id, owner, session)
    return TradeRepository(session).list_position_history(config_id)


@router.get("/trades/{config_id}", response_model=list[TradeResponseDto])
def list_trades_by_config(config_id: int, session: SessionDep, owner: CurrentOwnerDep) -> list[object]:
    return list_trades(config_id, session, owner)


@router.get("/strategy-configs/{config_id}/loc-orders", response_model=list[LocOrderResponseDto])
def list_loc_orders(config_id: int, session: SessionDep, owner: CurrentOwnerDep) -> list[object]:
    ensure_config_owner(config_id, owner, session)
    try:
        return LocOrderService(session).list_orders(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/strategy-configs/{config_id}/loc-orders",
    response_model=LocOrderResponseDto,
    status_code=status.HTTP_201_CREATED,
)
def create_loc_order(
    config_id: int,
    request: LocOrderCreateDto,
    session: SessionDep,
    owner: CurrentOwnerDep,
) -> object:
    ensure_config_owner(config_id, owner, session)
    try:
        return LocOrderService(session).create_from_daily_plan(config_id, request.memo)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/loc-orders/{order_id}/fill", response_model=LocOrderResponseDto)
def fill_loc_order(
    order_id: int,
    request: LocOrderFillDto,
    session: SessionDep,
    owner: CurrentOwnerDep,
) -> object:
    order = session.get(LocOrder, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"LOC order not found: {order_id}")
    ensure_config_owner(order.strategy_config_id, owner, session)
    try:
        return LocOrderService(session).fill_order(
            order_id,
            LocOrderFillRequest(
                quantity=request.quantity,
                price=request.price,
                fee=request.fee,
                memo=request.memo,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/loc-orders/{order_id}/unfilled", response_model=LocOrderResponseDto)
def mark_loc_order_unfilled(order_id: int, session: SessionDep, owner: CurrentOwnerDep) -> object:
    order = session.get(LocOrder, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"LOC order not found: {order_id}")
    ensure_config_owner(order.strategy_config_id, owner, session)
    try:
        return LocOrderService(session).mark_unfilled(order_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/trades/manual",
    response_model=ManualTradeResponseDto,
    status_code=status.HTTP_201_CREATED,
)
def record_manual_trade(
    request: ManualTradeRequestDto,
    session: SessionDep,
    owner: CurrentOwnerDep,
) -> object:
    ensure_config_owner(request.config_id, owner, session)
    service_request = ManualTradeRequest(
        config_id=request.config_id,
        side=request.side,
        trade_date=request.trade_date,
        quantity=request.quantity,
        price=request.price,
        fee=request.fee,
        limit_price=request.limit_price,
        sell_reason=request.sell_reason,
        source=request.source,
        mode=request.mode,
        position_id=request.position_id,
    )
    try:
        return ManualTradeService(session).record_manual_trade(service_request)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except ValidationAppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/trades/{trade_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trade(trade_id: int, session: SessionDep, owner: CurrentOwnerDep) -> None:
    ensure_trade_owner(trade_id, owner, session)
    try:
        ManualTradeService(session).delete_trade(trade_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except ValidationAppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc


@router.post(
    "/strategy-configs/{config_id}/signals/execute",
    response_model=SignalExecutionResponseDto,
)
def execute_signal(
    config_id: int,
    request: SignalExecutionRequestDto,
    session: SessionDep,
    owner: CurrentOwnerDep,
) -> object:
    ensure_config_owner(config_id, owner, session)
    service_request = SignalExecutionRequest(
        side=request.side,
        trade_date=request.trade_date,
        quantity=request.quantity,
        price=request.price,
        fee=request.fee,
        limit_price=request.limit_price,
        source=request.source,
        mode=request.mode,
        position_id=request.position_id,
        sell_reason=request.sell_reason,
    )
    try:
        return SignalExecutionService(session).execute_signal(config_id, service_request)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except ValidationAppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _ensure_config_exists(config_id: int, session: Session) -> None:
    if StrategyConfigRepository(session).get(config_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy config not found: {config_id}",
        )
