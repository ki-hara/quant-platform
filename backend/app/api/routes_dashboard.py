from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentOwnerDep, ensure_config_owner
from app.db.session import get_session
from app.dto.dashboard import DashboardResponseDto
from app.services.dashboard_service import DashboardService


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/{config_id}", response_model=DashboardResponseDto)
def get_dashboard(config_id: int, session: SessionDep, owner: CurrentOwnerDep) -> object:
    ensure_config_owner(config_id, owner, session)
    try:
        return DashboardService(session).get_dashboard(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
