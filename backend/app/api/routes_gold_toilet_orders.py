from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentOwnerDep, SessionDep
from app.dto.gold_toilet_orders import (
    GoldToiletAccountUpdateDto,
    GoldToiletManualOpenUpdateDto,
    GoldToiletOrderResponseDto,
    GoldToiletOrderSheetUpdateDto,
)
from app.infrastructure.market_data.regular_open_factory import build_regular_open_provider
from app.services.gold_toilet_order_interpreter import GoldToiletOrderInterpreter, MarketProvider


router = APIRouter(prefix="/api/gold-toilet", tags=["gold-toilet"])


def get_gold_toilet_market_provider() -> MarketProvider:
    return build_regular_open_provider()


MarketProviderDep = Annotated[MarketProvider, Depends(get_gold_toilet_market_provider)]


@router.get("/order-sheet", response_model=GoldToiletOrderResponseDto)
def get_order_sheet(
    order_date: date,
    session: SessionDep,
    owner: CurrentOwnerDep,
    provider: MarketProviderDep,
):
    return GoldToiletOrderInterpreter(session, provider).get(owner.id, order_date)


@router.put("/account", response_model=GoldToiletOrderResponseDto)
def update_account(
    request: GoldToiletAccountUpdateDto,
    session: SessionDep,
    owner: CurrentOwnerDep,
    provider: MarketProviderDep,
):
    return GoldToiletOrderInterpreter(session, provider).update_account(
        owner.id, request.capital, request.cash
    )


@router.put("/order-sheet/{order_date}", response_model=GoldToiletOrderResponseDto)
def update_order_sheet(
    order_date: date,
    request: GoldToiletOrderSheetUpdateDto,
    session: SessionDep,
    owner: CurrentOwnerDep,
    provider: MarketProviderDep,
):
    try:
        return GoldToiletOrderInterpreter(session, provider).update_sheet(
            owner.id,
            order_date,
            request.entry_percent,
            request.allocation_percent,
            request.loc_percent,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.put(
    "/order-sheet/{order_date}/manual-open",
    response_model=GoldToiletOrderResponseDto,
)
def set_manual_open(
    order_date: date,
    request: GoldToiletManualOpenUpdateDto,
    session: SessionDep,
    owner: CurrentOwnerDep,
    provider: MarketProviderDep,
):
    try:
        return GoldToiletOrderInterpreter(session, provider).set_manual_open(
            owner.id, order_date, request.market_open
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete(
    "/order-sheet/{order_date}/manual-open",
    response_model=GoldToiletOrderResponseDto,
)
def clear_manual_open(
    order_date: date,
    session: SessionDep,
    owner: CurrentOwnerDep,
    provider: MarketProviderDep,
):
    try:
        return GoldToiletOrderInterpreter(session, provider).clear_manual_open(
            owner.id, order_date
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
