from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.dto.trading_plan import (
    ChartResponseDto,
    ConfirmedModeUpdateDto,
    DailyPlanDto,
    MarketRefreshResponseDto,
    ModeRecommendationDto,
)
from app.infrastructure.market_data.base import MarketDataProvider
from app.services.chart_service import ChartService
from app.services.daily_plan_service import DailyPlanService
from app.services.market_refresh_service import MarketRefreshService, get_market_data_provider
from app.services.mode_service import ModeService


router = APIRouter(prefix="/api/strategy-configs", tags=["trading-plan"])


SessionDep = Annotated[Session, Depends(get_session)]
MarketProviderDep = Annotated[MarketDataProvider, Depends(get_market_data_provider)]


@router.get("/{config_id}/mode-recommendation", response_model=ModeRecommendationDto)
def get_mode_recommendation(
    config_id: int,
    session: SessionDep,
    as_of: date | None = None,
) -> object:
    try:
        return ModeService(session).get_mode_recommendation(config_id, as_of or date.today())
    except ValueError as exc:
        raise HTTPException(status_code=_status_code_for_error(str(exc)), detail=str(exc)) from exc


@router.put("/{config_id}/confirmed-mode", response_model=ModeRecommendationDto)
def update_confirmed_mode(
    config_id: int,
    request: ConfirmedModeUpdateDto,
    session: SessionDep,
) -> object:
    try:
        service = ModeService(session)
        if request.action == "set":
            if request.mode is None:
                raise ValueError("mode is required when action is set.")
            return service.set_confirmed_mode(config_id, request.mode)
        if request.action == "apply_recommendation":
            return service.apply_recommendation(config_id)
        raise ValueError(f"Unknown action: {request.action}")
    except ValueError as exc:
        raise HTTPException(status_code=_status_code_for_error(str(exc)), detail=str(exc)) from exc


@router.get("/{config_id}/mode-recommendations", response_model=list[ModeRecommendationDto])
def list_mode_recommendations(config_id: int, session: SessionDep) -> object:
    try:
        return ModeService(session).list_mode_recommendations(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=_status_code_for_error(str(exc)), detail=str(exc)) from exc


@router.get("/{config_id}/daily-plan", response_model=DailyPlanDto)
def get_daily_plan(
    config_id: int,
    session: SessionDep,
    today: date | None = None,
) -> object:
    try:
        return DailyPlanService(session).get_daily_plan(config_id, today or date.today())
    except ValueError as exc:
        raise HTTPException(status_code=_status_code_for_error(str(exc)), detail=str(exc)) from exc


@router.get("/{config_id}/chart", response_model=ChartResponseDto)
def get_chart(
    config_id: int,
    session: SessionDep,
    range: str = "6m",
    today: date | None = None,
) -> object:
    try:
        return ChartService(session).get_chart(config_id, range, today or date.today())
    except ValueError as exc:
        raise HTTPException(status_code=_status_code_for_error(str(exc)), detail=str(exc)) from exc


@router.post("/{config_id}/market-data/refresh", response_model=MarketRefreshResponseDto)
def refresh_market_data(
    config_id: int,
    session: SessionDep,
    provider: MarketProviderDep,
    today: date | None = None,
) -> object:
    try:
        return MarketRefreshService(session, provider).refresh(config_id, today or date.today())
    except ValueError as exc:
        raise HTTPException(status_code=_status_code_for_error(str(exc)), detail=str(exc)) from exc


def _status_code_for_error(message: str) -> int:
    return (
        status.HTTP_404_NOT_FOUND
        if "not found" in message.lower()
        else status.HTTP_422_UNPROCESSABLE_CONTENT
    )
