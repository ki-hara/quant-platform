from importlib import import_module

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_pin
from app.db.base import Base
from app.domain.models import Owner
from app.main import create_app


def migration_module():
    try:
        return import_module("app.db.migrations")
    except ModuleNotFoundError:
        pytest.fail("Versioned SQLite migration runner is missing.")


def test_fresh_database_records_latest_schema_version() -> None:
    migrations = migration_module()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    migrations.run_sqlite_migrations(engine)

    with engine.connect() as connection:
        versions = connection.scalars(
            text("SELECT version FROM schema_migrations ORDER BY version")
        ).all()
    assert versions == list(range(1, migrations.LATEST_SCHEMA_VERSION + 1))


def test_legacy_database_receives_all_required_tables_and_columns() -> None:
    migrations = migration_module()
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE strategy_configs (id INTEGER PRIMARY KEY)"))
        connection.execute(
            text(
                "CREATE TABLE backtest_daily_snapshots "
                "(backtest_run_id INTEGER NOT NULL, date DATE NOT NULL)"
            )
        )
        connection.execute(text("CREATE TABLE positions (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE trades (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE backtest_trades (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE owners (id VARCHAR(64) PRIMARY KEY)"))

    migrations.run_sqlite_migrations(engine)

    schema = inspect(engine)
    assert "strategy_config_snapshots" in schema.get_table_names()
    assert "portfolio_adjustments" in schema.get_table_names()
    assert "loc_orders" in schema.get_table_names()
    assert "archived_at" in {column["name"] for column in schema.get_columns("strategy_configs")}
    assert {"mode", "mode_rule_code"} <= {
        column["name"] for column in schema.get_columns("backtest_daily_snapshots")
    }
    assert "limit_price" in {column["name"] for column in schema.get_columns("positions")}
    assert {"limit_price", "position_id", "entry_date", "entry_price"} <= {
        column["name"] for column in schema.get_columns("trades")
    }
    assert {"holding_days", "open_position_count", "cash_after", "capital_after"} <= {
        column["name"] for column in schema.get_columns("backtest_trades")
    }
    assert {"pin_hash", "is_active", "is_admin", "created_at"} <= {
        column["name"] for column in schema.get_columns("owners")
    }


def test_migrations_are_idempotent() -> None:
    migrations = migration_module()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    migrations.run_sqlite_migrations(engine)
    migrations.run_sqlite_migrations(engine)

    with engine.connect() as connection:
        count = connection.scalar(text("SELECT COUNT(*) FROM schema_migrations"))
    assert count == migrations.LATEST_SCHEMA_VERSION


def test_create_app_uses_injected_database_for_lifespan_startup() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    app = create_app(database_engine=engine, session_factory=session_factory)
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200

    assert "schema_migrations" in inspect(engine).get_table_names()

def test_create_app_uses_injected_session_factory_for_requests() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with session_factory.begin() as session:
        session.add(
            Owner(
                id="injected-owner",
                name="Injected Owner",
                pin_hash=hash_pin("2468"),
                is_active=True,
                is_admin=False,
            )
        )

    app = create_app(database_engine=engine, session_factory=session_factory)
    with TestClient(app) as client:
        response = client.post(
            "/api/auth/login",
            json={"owner_id": "injected-owner", "pin": "2468"},
        )

    assert response.status_code == 200
    assert response.json()["owner"]["id"] == "injected-owner"


def test_migration_rebuilds_existing_loc_orders_foreign_key() -> None:
    migrations = migration_module()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE loc_orders"))
        connection.execute(
            text(
                """
                CREATE TABLE loc_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_config_id INTEGER NOT NULL,
                    order_date DATE NOT NULL,
                    symbol VARCHAR(32) NOT NULL,
                    limit_price NUMERIC(18, 6) NOT NULL,
                    recommended_quantity NUMERIC(18, 6) NOT NULL,
                    mode VARCHAR(10) NOT NULL,
                    status VARCHAR(10) NOT NULL,
                    trade_id INTEGER,
                    memo VARCHAR(500),
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    FOREIGN KEY(strategy_config_id) REFERENCES strategy_configs (id),
                    FOREIGN KEY(trade_id) REFERENCES trades (id)
                )
                """
            )
        )

    migrations.run_sqlite_migrations(engine)

    with engine.connect() as connection:
        foreign_keys = connection.execute(text("PRAGMA foreign_key_list(loc_orders)")).all()
    assert any(key[2] == "trades" and key[6] == "SET NULL" for key in foreign_keys)

def test_create_app_has_no_deprecated_startup_handlers() -> None:
    app = create_app()

    assert app.router.on_startup == []
