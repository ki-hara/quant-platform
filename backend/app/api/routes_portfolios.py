from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentOwnerDep, ensure_config_owner
from app.db.session import get_session
from app.dto.portfolios import PortfolioAdjustmentCreateDto, PortfolioAdjustmentResponseDto
from app.services.portfolio_adjustment_service import (
    PortfolioAdjustmentRequest,
    PortfolioAdjustmentService,
)


router = APIRouter(prefix="/api/strategy-configs", tags=["portfolios"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/{config_id}/portfolio-adjustments", response_model=list[PortfolioAdjustmentResponseDto])
def list_portfolio_adjustments(config_id: int, session: SessionDep, owner: CurrentOwnerDep) -> object:
    ensure_config_owner(config_id, owner, session)
    try:
        return PortfolioAdjustmentService(session).list_adjustments(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{config_id}/portfolio-adjustments",
    response_model=PortfolioAdjustmentResponseDto,
    status_code=status.HTTP_201_CREATED,
)
def create_portfolio_adjustment(
    config_id: int,
    request: PortfolioAdjustmentCreateDto,
    session: SessionDep,
    owner: CurrentOwnerDep,
) -> object:
    ensure_config_owner(config_id, owner, session)
    try:
        return PortfolioAdjustmentService(session).create_adjustment(
            config_id,
            PortfolioAdjustmentRequest(
                adjustment_date=request.date,
                cash_delta=request.cash_delta,
                capital_delta=request.capital_delta,
                memo=request.memo,
            ),
        )
    except ValueError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in str(exc).lower()
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
