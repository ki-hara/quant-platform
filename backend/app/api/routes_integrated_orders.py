from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentOwnerDep
from app.db.session import get_session
from app.dto.integrated_orders import (
    IntegratedOrderPreferenceDto,
    IntegratedOrderPreferenceUpdateDto,
    IntegratedOrdersResponseDto,
)
from app.services.integrated_order_service import IntegratedOrderService


router = APIRouter(prefix="/api/integrated-orders", tags=["integrated-orders"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("", response_model=IntegratedOrdersResponseDto)
def get_integrated_orders(session: SessionDep, owner: CurrentOwnerDep):
    return IntegratedOrderService(session).get_orders(owner.id)


@router.put(
    "/preferences/{config_id}",
    response_model=IntegratedOrderPreferenceDto,
)
def update_integrated_order_preference(
    config_id: int,
    request: IntegratedOrderPreferenceUpdateDto,
    session: SessionDep,
    owner: CurrentOwnerDep,
):
    try:
        return IntegratedOrderService(session).set_preference(owner.id, config_id, request.included)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
