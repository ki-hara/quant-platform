from datetime import datetime
from pathlib import Path
import sqlite3
import tempfile
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.api.deps import CurrentOwnerDep
from app.core.config import settings
from app.core.security import hash_pin
from app.db.session import get_session
from app.domain.models import MarketPrice, Owner, StrategyConfig, Trade


router = APIRouter(prefix="/api/admin", tags=["admin"])
SessionDep = Annotated[Session, Depends(get_session)]


class AdminUserDto(BaseModel):
    id: str
    name: str
    is_active: bool
    is_admin: bool
    is_guest: bool
    pin_reset_allowed: bool
    deactivate_allowed: bool
    created_at: datetime | None


class AdminSummaryDto(BaseModel):
    total_users: int
    active_users: int
    strategy_count: int
    trade_count: int
    database_backend: str
    database_path: str | None
    latest_market_data_date: str | None


class PinResetResponseDto(BaseModel):
    owner: AdminUserDto
    temporary_pin: str


def ensure_admin(owner: Owner) -> None:
    if not owner.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin permission is required.")


def admin_user_dto(owner: Owner, current_owner_id: str, admin_count: int) -> AdminUserDto:
    is_guest = owner.id == "guest"
    return AdminUserDto(
        id=owner.id,
        name=owner.name,
        is_active=owner.is_active,
        is_admin=owner.is_admin,
        is_guest=is_guest,
        pin_reset_allowed=not is_guest and owner.id != current_owner_id,
        deactivate_allowed=owner.id != current_owner_id and not (owner.is_admin and admin_count <= 1),
        created_at=owner.created_at,
    )


def active_admin_count(session: Session) -> int:
    return int(
        session.scalar(select(func.count()).select_from(Owner).where(Owner.is_active.is_(True), Owner.is_admin.is_(True)))
        or 0
    )


@router.get("/summary", response_model=AdminSummaryDto)
def get_admin_summary(owner: CurrentOwnerDep, session: SessionDep) -> AdminSummaryDto:
    ensure_admin(owner)
    url = make_url(settings.database_url)
    latest_market_date = session.scalar(select(func.max(MarketPrice.date)))
    return AdminSummaryDto(
        total_users=int(session.scalar(select(func.count()).select_from(Owner)) or 0),
        active_users=int(session.scalar(select(func.count()).select_from(Owner).where(Owner.is_active.is_(True))) or 0),
        strategy_count=int(session.scalar(select(func.count()).select_from(StrategyConfig)) or 0),
        trade_count=int(session.scalar(select(func.count()).select_from(Trade)) or 0),
        database_backend=url.get_backend_name(),
        database_path=url.database,
        latest_market_data_date=latest_market_date.isoformat() if latest_market_date else None,
    )


@router.get("/users", response_model=list[AdminUserDto])
def list_admin_users(owner: CurrentOwnerDep, session: SessionDep) -> list[AdminUserDto]:
    ensure_admin(owner)
    rows = session.scalars(select(Owner).order_by(Owner.created_at, Owner.id)).all()
    admin_count = active_admin_count(session)
    return [admin_user_dto(row, owner.id, admin_count) for row in rows]


@router.post("/users/{owner_id}/reset-pin", response_model=PinResetResponseDto)
def reset_user_pin(owner_id: str, owner: CurrentOwnerDep, session: SessionDep) -> PinResetResponseDto:
    ensure_admin(owner)
    target = session.get(Owner, owner_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if target.id == "guest":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Guest PIN cannot be reset.")
    if target.id == owner.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot reset your own PIN here.")
    target.pin_hash = hash_pin(settings.default_owner_pin)
    session.add(target)
    session.commit()
    session.refresh(target)
    return PinResetResponseDto(
        owner=admin_user_dto(target, owner.id, active_admin_count(session)),
        temporary_pin=settings.default_owner_pin,
    )


@router.post("/users/{owner_id}/deactivate", response_model=AdminUserDto)
def deactivate_user(owner_id: str, owner: CurrentOwnerDep, session: SessionDep) -> AdminUserDto:
    ensure_admin(owner)
    target = session.get(Owner, owner_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    admin_count = active_admin_count(session)
    if target.id == owner.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself.")
    if target.is_admin and admin_count <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate the last admin user.")
    target.is_active = False
    session.add(target)
    session.commit()
    session.refresh(target)
    return admin_user_dto(target, owner.id, active_admin_count(session))


@router.post("/users/{owner_id}/activate", response_model=AdminUserDto)
def activate_user(owner_id: str, owner: CurrentOwnerDep, session: SessionDep) -> AdminUserDto:
    ensure_admin(owner)
    target = session.get(Owner, owner_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    target.is_active = True
    session.add(target)
    session.commit()
    session.refresh(target)
    return admin_user_dto(target, owner.id, active_admin_count(session))


@router.get("/sqlite-backup")
def download_sqlite_backup(owner: CurrentOwnerDep) -> FileResponse:
    ensure_admin(owner)
    url = make_url(settings.database_url)
    if not url.get_backend_name().startswith("sqlite") or not url.database:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SQLite database backup is only available when SQLite is configured.",
        )
    if url.database == ":memory:":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="In-memory SQLite databases cannot be downloaded.",
        )

    source_path = Path(url.database).expanduser()
    if not source_path.is_absolute():
        source_path = Path.cwd() / source_path
    source_path = source_path.resolve()
    if not source_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SQLite database file not found: {source_path}",
        )

    backup_path = _create_sqlite_backup(source_path)
    filename = f"quant-platform-backup-{datetime.utcnow():%Y%m%d-%H%M%S}.db"
    return FileResponse(
        backup_path,
        media_type="application/octet-stream",
        filename=filename,
        background=BackgroundTask(lambda: backup_path.unlink(missing_ok=True)),
    )


def _create_sqlite_backup(source_path: Path) -> Path:
    temp_file = tempfile.NamedTemporaryFile(prefix="quant-platform-", suffix=".db", delete=False)
    temp_file.close()
    backup_path = Path(temp_file.name)
    try:
        with sqlite3.connect(source_path) as source, sqlite3.connect(backup_path) as destination:
            source.backup(destination)
    except Exception:
        backup_path.unlink(missing_ok=True)
        raise
    return backup_path
