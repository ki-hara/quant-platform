from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import parse_owner_token
from app.db.session import get_session
from app.domain.models import BacktestRun, Owner, Position, Trade
from app.infrastructure.repositories.strategies import StrategyConfigRepository


SessionDep = Annotated[Session, Depends(get_session)]


def get_current_owner(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> Owner:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required.")
    owner_id = parse_owner_token(token)
    if owner_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired login.")
    owner = session.get(Owner, owner_id)
    if owner is None or not owner.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user.")
    return owner


CurrentOwnerDep = Annotated[Owner, Depends(get_current_owner)]


def ensure_config_owner(config_id: int, owner: Owner, session: Session) -> None:
    config = StrategyConfigRepository(session).get(config_id)
    if config is None or config.owner_id != owner.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy config not found: {config_id}",
        )


def ensure_position_owner(position_id: int, owner: Owner, session: Session) -> Position:
    position = session.get(Position, position_id)
    if position is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Position not found: {position_id}")
    ensure_config_owner(position.strategy_config_id, owner, session)
    return position


def ensure_trade_owner(trade_id: int, owner: Owner, session: Session) -> Trade:
    trade = session.get(Trade, trade_id)
    if trade is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Trade not found: {trade_id}")
    ensure_config_owner(trade.strategy_config_id, owner, session)
    return trade


def ensure_backtest_owner(run_id: int, owner: Owner, session: Session) -> BacktestRun:
    run = session.get(BacktestRun, run_id)
    if run is None or run.owner_id != owner.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest run not found: {run_id}",
        )
    return run
