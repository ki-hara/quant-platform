from collections.abc import Generator
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.seed import seed_default_owner
from app.db.session import get_session
from app.main import create_app
from app.dto.market_data import OhlcvDto
from app.domain.enums import BacktestModePolicy, BacktestPositionSizingPolicy
from app.strategy_engine.dynamic_wave import DynamicWaveStrategy
from tests.fixtures import simple_prices


class FakeMarketDataService:
    def __init__(self) -> None:
        self.calls = []

    def get_ohlcv(self, symbol, start_date, end_date):
        self.calls.append((symbol, start_date, end_date))
        prices = [
            price
            for price in simple_prices()
            if price.symbol == symbol and start_date <= price.date <= end_date
        ]
        lookahead = OhlcvDto(
            symbol="TEST",
            date=date(2026, 1, 7),
            open=Decimal("113"),
            high=Decimal("113"),
            low=Decimal("113"),
            close=Decimal("113"),
            volume=Decimal("1000"),
        )
        if symbol == lookahead.symbol and start_date <= lookahead.date <= end_date:
            prices.append(lookahead)
        return prices


@pytest.fixture
def api_client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as seed_session:
        seed_default_owner(seed_session, "default")

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    from app.api.routes_backtests import get_market_data_service

    fake_market_data_service = FakeMarketDataService()
    app = create_app(database_engine=engine, session_factory=lambda: Session(engine))
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_market_data_service] = lambda: fake_market_data_service
    app.state.fake_market_data_service = fake_market_data_service
    client = TestClient(app)
    login_response = client.post("/api/auth/login", json={"owner_id": "default", "pin": "0000"})
    assert login_response.status_code == 200
    client.headers.update({"Authorization": f"Bearer {login_response.json()['token']}"})
    yield client
    client.close()
    app.dependency_overrides.clear()


def create_config(api_client: TestClient) -> int:
    response = api_client.post(
        "/api/strategy-configs",
        json={
            "name": "Backtest Strategy",
            "strategy_type": "dynamic_wave",
            "symbol": "TEST",
            "initial_capital": "1000",
            "fee_rate": "0.001",
            "slippage_rate": "0",
            "settings_json": DynamicWaveStrategy.default_settings(),
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_post_backtests_returns_completed_run_with_fixture_market_data(
    api_client: TestClient,
) -> None:
    config_id = create_config(api_client)

    response = api_client.post(
        "/api/backtests",
        json={
            "config_id": config_id,
            "start_date": "2026-01-01",
            "end_date": "2026-01-06",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["status"] == "completed"
    assert body["initial_capital"] == "1000.000000"
    assert body["final_capital"] is not None
    assert body["total_return"] is not None
    assert body["max_drawdown"] is not None
    assert body["win_rate"] is not None
    assert body["total_trades"] >= 0
    assert api_client.app.state.fake_market_data_service.calls[-1] == (
        "TEST",
        date(2026, 1, 1),
        date(2026, 1, 6) + timedelta(days=14),
    )

    daily = api_client.get(f"/api/backtests/{body['id']}/daily.csv")
    assert "2026-01-06" in daily.text
    assert "2026-01-07" not in daily.text


def test_backtest_csv_endpoints_stream_attachments(api_client: TestClient) -> None:
    config_id = create_config(api_client)
    run = api_client.post(
        "/api/backtests",
        json={
            "config_id": config_id,
            "start_date": "2026-01-01",
            "end_date": "2026-01-06",
        },
    ).json()

    daily = api_client.get(f"/api/backtests/{run['id']}/daily.csv")
    trades = api_client.get(f"/api/backtests/{run['id']}/trades.csv")
    summary = api_client.get(f"/api/backtests/{run['id']}/summary.csv")

    assert daily.status_code == 200
    assert daily.headers["content-type"].startswith("text/csv")
    assert daily.headers["content-disposition"] == (
        f'attachment; filename="backtest-{run["id"]}-daily.csv"'
    )
    assert "date,capital,cash,position_value,total_asset,drawdown,cumulative_fees,mode,mode_rule_code" in daily.text

    assert trades.status_code == 200
    assert trades.headers["content-type"].startswith("text/csv")
    assert trades.headers["content-disposition"] == (
        f'attachment; filename="backtest-{run["id"]}-trades.csv"'
    )
    assert (
        "date,side,quantity,price,fee,realized_pnl,sell_reason,source,holding_days,"
        "open_position_count,cash_after,capital_after"
    ) in trades.text
    assert "profit_target,signal_execution,1,0,1015.993520,1000.000000" in trades.text

    assert summary.status_code == 200
    assert summary.headers["content-type"].startswith("text/csv")
    assert summary.headers["content-disposition"] == (
        f'attachment; filename="backtest-{run["id"]}-summary.csv"'
    )
    assert "id,status,start_date,end_date,initial_capital,final_capital" in summary.text


def test_post_backtest_accepts_fixed_aggressive_policy_and_exports_mode(
    api_client: TestClient,
) -> None:
    config_id = create_config(api_client)

    response = api_client.post(
        "/api/backtests",
        json={
            "config_id": config_id,
            "start_date": "2026-01-01",
            "end_date": "2026-01-06",
            "mode_policy": BacktestModePolicy.FIXED_AGGRESSIVE.value,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["strategy_config_snapshot_json"]["mode_policy"] == "fixed_aggressive"
    daily = api_client.get(f"/api/backtests/{body['id']}/daily.csv")
    assert "aggressive,fixed_aggressive" in daily.text


def test_post_backtest_persists_position_sizing_policy_in_snapshot(
    api_client: TestClient,
) -> None:
    config_id = create_config(api_client)

    response = api_client.post(
        "/api/backtests",
        json={
            "config_id": config_id,
            "start_date": "2026-01-01",
            "end_date": "2026-01-06",
            "position_sizing_policy": BacktestPositionSizingPolicy.FULL_ALLOCATION.value,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["strategy_config_snapshot_json"]["position_sizing_policy"] == "full_allocation"
