from importlib import import_module

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
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
    assert versions == [migrations.LATEST_SCHEMA_VERSION]


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
    assert count == 1


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


def test_create_app_has_no_deprecated_startup_handlers() -> None:
    app = create_app()

    assert app.router.on_startup == []
