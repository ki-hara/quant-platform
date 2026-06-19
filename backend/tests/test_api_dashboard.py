from collections.abc import Generator
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.seed import seed_default_owner
from app.db.session import get_session
from app.dto.market_data import OhlcvDto
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.main import create_app
from app.strategy_engine.dynamic_wave import DynamicWaveStrategy


def test_health_endpoint_returns_ok(test_client: TestClient) -> None:
    response = test_client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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

    app = create_app()
    app.state.test_engine = engine
    app.dependency_overrides[get_session] = override_session
    client = TestClient(app)
    yield client
    client.close()
    app.dependency_overrides.clear()


def test_get_strategies_includes_dynamic_wave(api_client: TestClient) -> None:
    response = api_client.get("/api/strategies")

    assert response.status_code == 200
    strategies = response.json()
    assert {"type": "dynamic_wave", "name": "Dynamic Wave Strategy"} in strategies


def test_get_dynamic_wave_schema_returns_settings_fields(api_client: TestClient) -> None:
    response = api_client.get("/api/strategies/dynamic_wave/schema")

    assert response.status_code == 200
    body = response.json()
    assert body["strategy_type"] == "dynamic_wave"
    assert body["schema"]["fields"]["safe"]["split_count"] == 7
    assert body["schema"]["fields"]["aggressive"]["buy_threshold_percent"] == 5


def test_post_strategy_configs_creates_config(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/strategy-configs",
        json={
            "name": "API Strategy",
            "strategy_type": "dynamic_wave",
            "symbol": "TEST",
            "initial_capital": "1000",
            "fee_rate": "0.001",
            "slippage_rate": "0",
            "settings_json": DynamicWaveStrategy.default_settings(),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["name"] == "API Strategy"
    assert body["strategy_type"] == "dynamic_wave"
    assert body["symbol"] == "TEST"
    assert body["initial_capital"] == "1000.000000"


def test_get_dashboard_returns_metric_fields(api_client: TestClient) -> None:
    create_response = api_client.post(
        "/api/strategy-configs",
        json={
            "name": "Dashboard Strategy",
            "strategy_type": "dynamic_wave",
            "symbol": "TEST",
            "initial_capital": "1000",
            "fee_rate": "0.001",
            "slippage_rate": "0",
            "settings_json": DynamicWaveStrategy.default_settings(),
        },
    )
    config_id = create_response.json()["id"]

    with Session(api_client.app.state.test_engine) as session:
        MarketPriceRepository(session).upsert_prices(
            "finance-data-reader",
            [
                OhlcvDto(
                    symbol="TEST",
                    date=date(2026, 1, 1),
                    open=Decimal("100"),
                    high=Decimal("100"),
                    low=Decimal("100"),
                    close=Decimal("100"),
                    volume=1000,
                ),
                OhlcvDto(
                    symbol="TEST",
                    date=date(2026, 1, 2),
                    open=Decimal("102"),
                    high=Decimal("102"),
                    low=Decimal("102"),
                    close=Decimal("102"),
                    volume=1000,
                ),
            ],
        )
        session.commit()

    response = api_client.get(f"/api/dashboard/{config_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["config"]["id"] == config_id
    assert body["portfolio"]["cash"] == "1000.000000"
    assert body["latest_price"]["close"] == "102.000000"
    assert body["total_asset"] == "1000.000000"
    assert body["signals"]["available"] is True
