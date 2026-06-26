from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentOwnerDep, ensure_config_owner
from app.db.session import get_session
from app.dto.strategies import (
    StrategyConfigCreateDto,
    StrategyConfigResponseDto,
    StrategyConfigUpdateDto,
    StrategyDto,
    StrategySchemaDto,
)
from app.services.strategy_config_service import (
    StrategyConfigCreateRequest,
    StrategyConfigUpdateRequest,
    StrategyConfigService,
)
from app.strategy_engine.registry import registry


router = APIRouter(prefix="/api", tags=["strategies"])


SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/strategies", response_model=list[StrategyDto])
def list_strategies() -> list[dict[str, str]]:
    return registry.list()


@router.get("/strategies/{strategy_type}/schema", response_model=StrategySchemaDto)
def get_strategy_schema(strategy_type: str) -> StrategySchemaDto:
    try:
        strategy = registry.create(strategy_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return StrategySchemaDto(strategy_type=strategy_type, schema_=strategy.get_settings_schema())


@router.get("/strategy-configs", response_model=list[StrategyConfigResponseDto])
def list_strategy_configs(session: SessionDep, owner: CurrentOwnerDep) -> list[object]:
    return StrategyConfigService(session).list_configs(owner.id)


@router.post(
    "/strategy-configs",
    response_model=StrategyConfigResponseDto,
    status_code=status.HTTP_201_CREATED,
)
def create_strategy_config(
    request: StrategyConfigCreateDto,
    session: SessionDep,
    owner: CurrentOwnerDep,
) -> object:
    service_request = StrategyConfigCreateRequest(
        name=request.name,
        strategy_type=request.strategy_type,
        symbol=request.symbol,
        initial_capital=request.initial_capital,
        fee_rate=request.fee_rate,
        slippage_rate=request.slippage_rate,
        settings_json=request.settings_json,
    )
    try:
        return StrategyConfigService(session).create_config(
            owner.id,
            service_request,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/strategy-configs/{config_id}", response_model=StrategyConfigResponseDto)
def get_strategy_config(config_id: int, session: SessionDep, owner: CurrentOwnerDep) -> object:
    ensure_config_owner(config_id, owner, session)
    try:
        return StrategyConfigService(session).get_config(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/strategy-configs/{config_id}", response_model=StrategyConfigResponseDto)
def update_strategy_config(
    config_id: int,
    request: StrategyConfigUpdateDto,
    session: SessionDep,
    owner: CurrentOwnerDep,
) -> object:
    ensure_config_owner(config_id, owner, session)
    service_request = StrategyConfigUpdateRequest(
        name=request.name,
        strategy_type=request.strategy_type,
        symbol=request.symbol,
        initial_capital=request.initial_capital,
        fee_rate=request.fee_rate,
        slippage_rate=request.slippage_rate,
        settings_json=request.settings_json,
    )
    try:
        return StrategyConfigService(session).update_config(config_id, service_request)
    except ValueError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in str(exc).lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.delete("/strategy-configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_strategy_config(config_id: int, session: SessionDep, owner: CurrentOwnerDep) -> None:
    ensure_config_owner(config_id, owner, session)
    try:
        StrategyConfigService(session).archive_config(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
