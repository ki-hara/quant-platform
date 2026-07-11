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
from app.domain.enums import TradeSide, TradeSource
from app.infrastructure.repositories.market_data import MarketPriceRepository
from app.infrastructure.repositories.trades import TradeRepository
from app.main import create_app
import app.services.dashboard_service as dashboard_service_module
import app.services.fear_greed_service as fear_greed_service_module
from app.strategy_engine.dynamic_wave import DynamicWaveStrategy


def test_health_endpoint_returns_ok(test_client: TestClient) -> None:
    response = test_client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def _price(symbol: str, day: date, close: str) -> OhlcvDto:
    value = Decimal(close)
    return OhlcvDto(
        symbol=symbol,
        date=day,
        open=value,
        high=value,
        low=value,
        close=value,
        volume=1000,
    )


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

    app = create_app(database_engine=engine, session_factory=lambda: Session(engine))
    app.state.test_engine = engine
    app.dependency_overrides[get_session] = override_session
    client = TestClient(app)
    login_response = client.post("/api/auth/login", json={"owner_id": "default", "pin": "0000"})
    assert login_response.status_code == 200
    client.headers.update({"Authorization": f"Bearer {login_response.json()['token']}"})
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


def test_put_strategy_config_updates_existing_config(api_client: TestClient) -> None:
    create_response = api_client.post(
        "/api/strategy-configs",
        json={
            "name": "Original Strategy",
            "strategy_type": "dynamic_wave",
            "symbol": "TEST",
            "initial_capital": "1000",
            "fee_rate": "0.001",
            "slippage_rate": "0",
            "settings_json": DynamicWaveStrategy.default_settings(),
        },
    )
    config_id = create_response.json()["id"]

    response = api_client.put(
        f"/api/strategy-configs/{config_id}",
        json={
            "name": "Updated Strategy",
            "symbol": "QQQ",
            "settings_json": {
                **DynamicWaveStrategy.default_settings(),
                "capital_update": {"type": "calendar", "period": "monthly"},
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == config_id
    assert body["name"] == "Updated Strategy"
    assert body["symbol"] == "QQQ"
    assert body["settings_json"]["capital_update"] == {"type": "calendar", "period": "monthly"}


def test_delete_strategy_config_archives_and_hides_from_list(api_client: TestClient) -> None:
    create_response = api_client.post(
        "/api/strategy-configs",
        json={
            "name": "Delete Me",
            "strategy_type": "dynamic_wave",
            "symbol": "SOXL",
            "initial_capital": "1000",
            "fee_rate": "0.001",
            "slippage_rate": "0",
            "settings_json": DynamicWaveStrategy.default_settings(),
        },
    )
    config_id = create_response.json()["id"]

    delete_response = api_client.delete(f"/api/strategy-configs/{config_id}")
    list_response = api_client.get("/api/strategy-configs")

    assert delete_response.status_code == 204
    assert config_id not in [row["id"] for row in list_response.json()]


def test_portfolio_adjustment_api_updates_cash_and_capital(api_client: TestClient) -> None:
    create_response = api_client.post(
        "/api/strategy-configs",
        json={
            "name": "Adjust",
            "strategy_type": "dynamic_wave",
            "symbol": "SOXL",
            "initial_capital": "1000",
            "fee_rate": "0.001",
            "slippage_rate": "0",
            "settings_json": DynamicWaveStrategy.default_settings(),
        },
    )
    config_id = create_response.json()["id"]

    response = api_client.post(
        f"/api/strategy-configs/{config_id}/portfolio-adjustments",
        json={
            "date": "2026-06-26",
            "cash_delta": "100",
            "capital_delta": "50",
            "memo": "deposit",
        },
    )
    list_response = api_client.get(f"/api/strategy-configs/{config_id}/portfolio-adjustments")
    dashboard_response = api_client.get(f"/api/dashboard/{config_id}")

    assert response.status_code == 201
    assert response.json()["cash_delta"] == "100.000000"
    assert len(list_response.json()) == 1
    assert dashboard_response.json()["portfolio"]["cash"] == "1100.000000"
    assert dashboard_response.json()["portfolio"]["capital"] == "1050.000000"


def test_get_dashboard_reads_cached_prices_with_configured_provider_key(api_client: TestClient) -> None:
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
            "finance_data_reader",
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


def test_get_dashboard_includes_market_sentiment(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        fear_greed_service_module.FearGreedService,
        "get_current",
        lambda self: fear_greed_service_module.MarketSentiment(
            score=24,
            rating="fear",
            label="공포",
            as_of=date(2026, 7, 1),
            source="CNN Fear & Greed",
            available=True,
        ),
    )
    create_response = api_client.post(
        "/api/strategy-configs",
        json={
            "name": "Sentiment Strategy",
            "strategy_type": "dynamic_wave",
            "symbol": "SOXL",
            "initial_capital": "1000",
            "fee_rate": "0.001",
            "slippage_rate": "0",
            "settings_json": DynamicWaveStrategy.default_settings(),
        },
    )
    config_id = create_response.json()["id"]

    response = api_client.get(f"/api/dashboard/{config_id}")

    assert response.status_code == 200
    sentiment = response.json()["market_sentiment"]
    assert sentiment["score"] == 24
    assert sentiment["label"] == "공포"
    assert sentiment["source"] == "CNN Fear & Greed"


def test_get_dashboard_auto_applies_capital_update_once(api_client: TestClient) -> None:
    settings = DynamicWaveStrategy.default_settings()
    settings["capital_update"] = {"type": "trading_days", "interval": 10, "period": "monthly"}
    settings["profit_compounding_rate"] = 60
    create_response = api_client.post(
        "/api/strategy-configs",
        json={
            "name": "Auto Capital",
            "strategy_type": "dynamic_wave",
            "symbol": "TEST",
            "initial_capital": "1000",
            "fee_rate": "0.001",
            "slippage_rate": "0",
            "settings_json": settings,
        },
    )
    config_id = create_response.json()["id"]
    trading_days = [
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 5),
        date(2026, 1, 6),
        date(2026, 1, 7),
        date(2026, 1, 8),
        date(2026, 1, 9),
        date(2026, 1, 12),
        date(2026, 1, 13),
        date(2026, 1, 14),
        date(2026, 1, 15),
        date(2026, 1, 16),
    ]

    with Session(api_client.app.state.test_engine) as session:
        MarketPriceRepository(session).upsert_prices(
            "finance_data_reader",
            [
                OhlcvDto(
                    symbol="TEST",
                    date=day,
                    open=Decimal("100"),
                    high=Decimal("100"),
                    low=Decimal("100"),
                    close=Decimal("100"),
                    volume=1000,
                )
                for day in trading_days
            ],
        )
        TradeRepository(session).create(
            strategy_config_id=config_id,
            trade_date=date(2026, 1, 2),
            side=TradeSide.SELL,
            quantity=Decimal("1"),
            price=Decimal("100"),
            fee=Decimal("0"),
            realized_pnl=Decimal("100"),
            sell_reason="profit_target",
            source=TradeSource.MANUAL,
        )
        session.commit()

    first = api_client.get(f"/api/dashboard/{config_id}")
    second = api_client.get(f"/api/dashboard/{config_id}")
    adjustments = api_client.get(f"/api/strategy-configs/{config_id}/portfolio-adjustments")

    assert first.status_code == 200
    assert first.json()["portfolio"]["capital"] == "1060.000000"
    assert first.json()["capital_update"]["applied"] is True
    assert first.json()["capital_update"]["capital_delta"] == "60.000000"
    assert second.json()["portfolio"]["capital"] == "1060.000000"
    auto_adjustments = [
        row for row in adjustments.json() if row["source"] == "strategy_capital_update"
    ]
    assert len(auto_adjustments) == 1
    assert auto_adjustments[0]["period_start_date"] == "2026-01-02"
    assert auto_adjustments[0]["period_end_date"] == "2026-01-16"


def test_capital_update_predicts_next_us_trading_day_with_holidays(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        dashboard_service_module,
        "current_market_date",
        lambda symbol: date(2026, 6, 30),
    )
    settings = DynamicWaveStrategy.default_settings()
    settings["capital_update"] = {"type": "trading_days", "interval": 10, "period": "monthly"}
    create_response = api_client.post(
        "/api/strategy-configs",
        json={
            "name": "US Calendar Capital",
            "strategy_type": "dynamic_wave",
            "symbol": "SOXL",
            "initial_capital": "10000",
            "fee_rate": "0.001",
            "slippage_rate": "0",
            "settings_json": settings,
        },
    )
    config_id = create_response.json()["id"]

    with Session(api_client.app.state.test_engine) as session:
        MarketPriceRepository(session).upsert_prices(
            "finance_data_reader",
            [_price("SOXL", date(2026, 6, 26), "100")],
        )
        TradeRepository(session).create(
            strategy_config_id=config_id,
            trade_date=date(2026, 6, 25),
            side=TradeSide.BUY,
            quantity=Decimal("1"),
            price=Decimal("100"),
            fee=Decimal("0"),
            realized_pnl=Decimal("0"),
            sell_reason=None,
            source=TradeSource.MANUAL,
        )
        session.commit()

    response = api_client.get(f"/api/dashboard/{config_id}")

    assert response.status_code == 200
    capital_update = response.json()["capital_update"]
    assert capital_update["status"] == "waiting"
    assert capital_update["elapsed_trading_days"] == 3
    assert capital_update["next_update_date"] == "2026-07-10"
    assert capital_update["period_start_date"] == "2026-06-25"
    assert capital_update["period_end_date"] == "2026-07-10"


def test_capital_update_applies_on_exchange_calendar_due_date(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        dashboard_service_module,
        "current_market_date",
        lambda symbol: date(2026, 7, 10),
    )
    settings = DynamicWaveStrategy.default_settings()
    settings["capital_update"] = {"type": "trading_days", "interval": 10, "period": "monthly"}
    settings["profit_compounding_rate"] = 60
    create_response = api_client.post(
        "/api/strategy-configs",
        json={
            "name": "US Calendar Apply",
            "strategy_type": "dynamic_wave",
            "symbol": "SOXL",
            "initial_capital": "10000",
            "fee_rate": "0.001",
            "slippage_rate": "0",
            "settings_json": settings,
        },
    )
    config_id = create_response.json()["id"]

    with Session(api_client.app.state.test_engine) as session:
        MarketPriceRepository(session).upsert_prices(
            "finance_data_reader",
            [_price("SOXL", date(2026, 6, 26), "100")],
        )
        trades = TradeRepository(session)
        trades.create(
            strategy_config_id=config_id,
            trade_date=date(2026, 6, 25),
            side=TradeSide.BUY,
            quantity=Decimal("1"),
            price=Decimal("100"),
            fee=Decimal("0"),
            realized_pnl=Decimal("0"),
            sell_reason=None,
            source=TradeSource.MANUAL,
        )
        trades.create(
            strategy_config_id=config_id,
            trade_date=date(2026, 7, 9),
            side=TradeSide.SELL,
            quantity=Decimal("1"),
            price=Decimal("200"),
            fee=Decimal("0"),
            realized_pnl=Decimal("100"),
            sell_reason="profit_target",
            source=TradeSource.MANUAL,
        )
        session.commit()

    response = api_client.get(f"/api/dashboard/{config_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["capital_update"]["applied"] is True
    assert body["capital_update"]["period_end_date"] == "2026-07-10"
    assert body["capital_update"]["capital_delta"] == "60.000000"
    assert body["portfolio"]["capital"] == "10060.000000"


def test_positions_missing_config_returns_404(api_client: TestClient) -> None:
    response = api_client.get("/api/positions/999")

    assert response.status_code == 404
    assert "Strategy config not found" in response.json()["detail"]


def test_trades_missing_config_returns_404(api_client: TestClient) -> None:
    response = api_client.get("/api/trades/999")

    assert response.status_code == 404
    assert "Strategy config not found" in response.json()["detail"]


def test_signal_execution_missing_config_returns_404(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/strategy-configs/999/signals/execute",
        json={
            "side": "buy",
            "trade_date": "2026-01-02",
            "quantity": "1",
            "price": "100",
            "fee": "0",
        },
    )

    assert response.status_code == 404


def test_signal_execution_missing_position_returns_404(api_client: TestClient) -> None:
    create_response = api_client.post(
        "/api/strategy-configs",
        json={
            "name": "Sell Strategy",
            "strategy_type": "dynamic_wave",
            "symbol": "TEST",
            "initial_capital": "1000",
            "fee_rate": "0.001",
            "slippage_rate": "0",
            "settings_json": DynamicWaveStrategy.default_settings(),
        },
    )
    config_id = create_response.json()["id"]

    response = api_client.post(
        f"/api/strategy-configs/{config_id}/signals/execute",
        json={
            "side": "sell",
            "trade_date": "2026-01-02",
            "quantity": "1",
            "price": "100",
            "fee": "0",
            "position_id": 999,
        },
    )

    assert response.status_code == 404


def test_invalid_signal_fill_returns_400(api_client: TestClient) -> None:
    create_response = api_client.post(
        "/api/strategy-configs",
        json={
            "name": "Invalid Fill Strategy",
            "strategy_type": "dynamic_wave",
            "symbol": "TEST",
            "initial_capital": "1000",
            "fee_rate": "0.001",
            "slippage_rate": "0",
            "settings_json": DynamicWaveStrategy.default_settings(),
        },
    )
    config_id = create_response.json()["id"]

    response = api_client.post(
        f"/api/strategy-configs/{config_id}/signals/execute",
        json={
            "side": "buy",
            "trade_date": "2026-01-02",
            "quantity": "0",
            "price": "100",
            "fee": "0",
        },
    )

    assert response.status_code == 400


def test_post_manual_trade_buy_creates_trade_position_and_updates_cash(api_client: TestClient) -> None:
    create_response = api_client.post(
        "/api/strategy-configs",
        json={
            "name": "Manual Buy Strategy",
            "strategy_type": "dynamic_wave",
            "symbol": "TEST",
            "initial_capital": "1000",
            "fee_rate": "0.001",
            "slippage_rate": "0",
            "settings_json": DynamicWaveStrategy.default_settings(),
        },
    )
    config_id = create_response.json()["id"]

    response = api_client.post(
        "/api/trades/manual",
        json={
            "config_id": config_id,
            "trade_date": "2026-01-02",
            "side": "buy",
            "quantity": "2",
            "price": "100",
            "fee": "1.25",
            "source": "manual",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["trade"]["source"] == "manual"
    assert body["trade"]["side"] == "buy"
    assert body["cash"] == "798.750000"
    positions = api_client.get(f"/api/strategy-configs/{config_id}/positions").json()
    assert len(positions) == 1
    assert positions[0]["buy_fee"] == "1.250000"


def test_post_manual_trade_sell_without_position_returns_400(
    api_client: TestClient,
) -> None:
    create_response = api_client.post(
        "/api/strategy-configs",
        json={
            "name": "Manual Correction Strategy",
            "strategy_type": "dynamic_wave",
            "symbol": "TEST",
            "initial_capital": "1000",
            "fee_rate": "0.001",
            "slippage_rate": "0",
            "settings_json": DynamicWaveStrategy.default_settings(),
        },
    )
    config_id = create_response.json()["id"]

    response = api_client.post(
        "/api/trades/manual",
        json={
            "config_id": config_id,
            "trade_date": "2026-01-03",
            "side": "sell",
            "quantity": "1",
            "price": "110",
            "fee": "0.50",
            "realized_pnl": "9.50",
            "sell_reason": "broker_correction",
            "source": "correction",
        },
    )

    assert response.status_code == 400
    assert "position_id" in response.json()["detail"]


def test_put_strategy_config_rejects_initial_capital_change(api_client: TestClient) -> None:
    create_response = api_client.post(
        "/api/strategy-configs",
        json={
            "name": "Capital Guard",
            "strategy_type": "dynamic_wave",
            "symbol": "TEST",
            "initial_capital": "1000",
            "fee_rate": "0.001",
            "slippage_rate": "0",
            "settings_json": DynamicWaveStrategy.default_settings(),
        },
    )
    config_id = create_response.json()["id"]

    response = api_client.put(
        f"/api/strategy-configs/{config_id}",
        json={"initial_capital": "2000"},
    )

    assert response.status_code == 400
    assert "initial_capital" in response.json()["detail"]
