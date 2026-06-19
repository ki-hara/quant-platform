from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.db.session import get_session
from app.dto.dashboard import PositionDto
from app.dto.trades import (
    SignalExecutionRequestDto,
    SignalExecutionResponseDto,
    TradeResponseDto,
)
from app.infrastructure.repositories.portfolios import PositionRepository
from app.infrastructure.repositories.strategies import StrategyConfigRepository
from app.infrastructure.repositories.trades import TradeRepository
from app.services.signal_execution_service import (
    SignalExecutionRequest,
    SignalExecutionService,
)


router = APIRouter(prefix="/api", tags=["trades"])


SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/strategy-configs/{config_id}/positions", response_model=list[PositionDto])
def list_positions(config_id: int, session: SessionDep) -> list[object]:
    _ensure_config_exists(config_id, session)
    return PositionRepository(session).list_by_strategy_config(config_id)


@router.get("/positions/{config_id}", response_model=list[PositionDto])
def list_positions_by_config(config_id: int, session: SessionDep) -> list[object]:
    return list_positions(config_id, session)


@router.get("/strategy-configs/{config_id}/trades", response_model=list[TradeResponseDto])
def list_trades(config_id: int, session: SessionDep) -> list[object]:
    _ensure_config_exists(config_id, session)
    return TradeRepository(session).list_by_strategy_config(config_id)


@router.get("/trades/{config_id}", response_model=list[TradeResponseDto])
def list_trades_by_config(config_id: int, session: SessionDep) -> list[object]:
    return list_trades(config_id, session)


@router.post(
    "/strategy-configs/{config_id}/signals/execute",
    response_model=SignalExecutionResponseDto,
)
def execute_signal(
    config_id: int,
    request: SignalExecutionRequestDto,
    session: SessionDep,
) -> object:
    service_request = SignalExecutionRequest(
        side=request.side,
        trade_date=request.trade_date,
        quantity=request.quantity,
        price=request.price,
        fee=request.fee,
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
