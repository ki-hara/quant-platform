import csv
from io import StringIO
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError, MarketDataError
from app.db.session import get_session
from app.dto.backtests import BacktestCreateDto, BacktestRunResponseDto
from app.infrastructure.market_data.cached_provider import CachedMarketDataProvider
from app.infrastructure.market_data.finance_data_reader_provider import FinanceDataReaderProvider
from app.infrastructure.repositories.backtests import BacktestRepository
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.services.backtest_service import BacktestRunRequest, BacktestService
from app.services.market_data_service import MarketDataService


router = APIRouter(prefix="/api/backtests", tags=["backtests"])


SessionDep = Annotated[Session, Depends(get_session)]


def get_market_data_service(session: SessionDep) -> MarketDataService:
    provider = CachedMarketDataProvider(
        settings.market_data_provider,
        MarketPriceRepository(session),
        FinanceDataReaderProvider(),
    )
    return MarketDataService(provider)


MarketDataServiceDep = Annotated[MarketDataService, Depends(get_market_data_service)]


@router.post("", response_model=BacktestRunResponseDto, status_code=status.HTTP_201_CREATED)
def create_backtest(
    request: BacktestCreateDto,
    session: SessionDep,
    market_data_service: MarketDataServiceDep,
) -> object:
    if request.end_date < request.start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be on or after start_date",
        )
    try:
        return BacktestService(session, market_data_service).run_backtest(
            BacktestRunRequest(
                config_id=request.config_id,
                start_date=request.start_date,
                end_date=request.end_date,
                mode_policy=request.mode_policy,
            )
        )
    except MarketDataError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message) from exc
    except AppError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except ValueError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in str(exc).lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/{run_id}", response_model=BacktestRunResponseDto)
def get_backtest(run_id: int, session: SessionDep) -> object:
    return _get_run_or_404(run_id, session)


@router.get("/{run_id}/daily.csv")
def download_daily_csv(run_id: int, session: SessionDep) -> StreamingResponse:
    run = _get_run_or_404(run_id, session)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "date",
            "capital",
            "cash",
            "position_value",
            "total_asset",
            "drawdown",
            "cumulative_fees",
            "mode",
            "mode_rule_code",
        ]
    )
    for snapshot in sorted(run.daily_snapshots, key=lambda item: item.date):
        writer.writerow(
            [
                snapshot.date.isoformat(),
                snapshot.capital,
                snapshot.cash,
                snapshot.position_value,
                snapshot.total_asset,
                snapshot.drawdown,
                snapshot.cumulative_fees,
                snapshot.mode,
                snapshot.mode_rule_code or "",
            ]
        )
    return _csv_response(output, f"backtest-{run_id}-daily.csv")


@router.get("/{run_id}/trades.csv")
def download_trades_csv(run_id: int, session: SessionDep) -> StreamingResponse:
    run = _get_run_or_404(run_id, session)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "side", "quantity", "price", "fee", "realized_pnl", "sell_reason", "source"])
    for trade in sorted(run.trades, key=lambda item: (item.date, item.id)):
        writer.writerow(
            [
                trade.date.isoformat(),
                trade.side,
                trade.quantity,
                trade.price,
                trade.fee,
                trade.realized_pnl,
                trade.sell_reason or "",
                trade.source,
            ]
        )
    return _csv_response(output, f"backtest-{run_id}-trades.csv")


@router.get("/{run_id}/summary.csv")
def download_summary_csv(run_id: int, session: SessionDep) -> StreamingResponse:
    run = _get_run_or_404(run_id, session)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "status",
            "start_date",
            "end_date",
            "initial_capital",
            "final_capital",
            "total_return",
            "max_drawdown",
            "win_rate",
            "total_trades",
        ]
    )
    writer.writerow(
        [
            run.id,
            run.status,
            run.start_date.isoformat(),
            run.end_date.isoformat(),
            run.initial_capital,
            run.final_capital,
            run.total_return,
            run.max_drawdown,
            run.win_rate,
            run.total_trades,
        ]
    )
    return _csv_response(output, f"backtest-{run_id}-summary.csv")


def _get_run_or_404(run_id: int, session: Session) -> object:
    run = BacktestRepository(session).get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest run not found: {run_id}",
        )
    return run


def _csv_response(output: StringIO, filename: str) -> StreamingResponse:
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
