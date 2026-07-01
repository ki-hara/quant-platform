from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CurrentOwnerDep
from app.core.security import create_owner_token, hash_pin, verify_pin
from app.db.session import get_session
from app.domain.models import Owner


router = APIRouter(prefix="/api/auth", tags=["auth"])

SessionDep = Annotated[Session, Depends(get_session)]


class OwnerDto(BaseModel):
    id: str
    name: str
    is_admin: bool = False
    is_guest: bool = False
    pin_change_allowed: bool = True

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def set_computed_flags(self) -> "OwnerDto":
        self.is_guest = self.id == "guest"
        self.pin_change_allowed = self.id != "guest"
        return self


class OwnerCreateDto(BaseModel):
    id: str = Field(min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=255)
    pin: str = Field(min_length=4, max_length=32)


class LoginRequestDto(BaseModel):
    owner_id: str
    pin: str


class LoginResponseDto(BaseModel):
    token: str
    owner: OwnerDto


class PinChangeDto(BaseModel):
    current_pin: str = Field(min_length=4, max_length=32)
    new_pin: str = Field(min_length=4, max_length=32)


@router.get("/owners", response_model=list[OwnerDto])
def list_owners(session: SessionDep) -> list[Owner]:
    stmt = select(Owner).where(Owner.is_active.is_(True)).order_by(Owner.created_at, Owner.id)
    return list(session.scalars(stmt))


@router.post("/owners", response_model=OwnerDto, status_code=status.HTTP_201_CREATED)
def create_owner(request: OwnerCreateDto, session: SessionDep) -> Owner:
    if request.id == "guest":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Guest user is reserved.")
    owner = Owner(id=request.id, name=request.name, pin_hash=hash_pin(request.pin), is_active=True, is_admin=False)
    try:
        session.add(owner)
        session.commit()
        session.refresh(owner)
        return owner
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User ID already exists.") from exc


@router.post("/login", response_model=LoginResponseDto)
def login(request: LoginRequestDto, session: SessionDep) -> LoginResponseDto:
    owner = session.get(Owner, request.owner_id)
    if owner is None or not owner.is_active or not verify_pin(request.pin, owner.pin_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User or PIN is incorrect.")
    return LoginResponseDto(token=create_owner_token(owner.id), owner=OwnerDto.model_validate(owner))


@router.get("/me", response_model=OwnerDto)
def me(owner: CurrentOwnerDep) -> Owner:
    return owner


@router.post("/me/change-pin", response_model=OwnerDto)
def change_my_pin(request: PinChangeDto, owner: CurrentOwnerDep, session: SessionDep) -> Owner:
    if owner.id == "guest":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Guest PIN cannot be changed.")
    if not verify_pin(request.current_pin, owner.pin_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current PIN is incorrect.")
    owner.pin_hash = hash_pin(request.new_pin)
    session.add(owner)
    session.commit()
    session.refresh(owner)
    return owner
