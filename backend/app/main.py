from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.routes_admin import router as admin_router
from app.api.routes_auth import router as auth_router
from app.api.routes_backtests import router as backtests_router
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_portfolios import router as portfolios_router
from app.api.routes_trading_plan import router as trading_plan_router
from app.api.routes_strategies import router as strategies_router
from app.api.routes_trades import router as trades_router
from app.core.config import settings, validate_production_settings
from app.db.base import Base
from app.db.seed import seed_default_owner
from app.db.session import SessionLocal, engine


def create_app() -> FastAPI:
    app = FastAPI(title="Quant Strategy Platform", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(strategies_router)
    app.include_router(trading_plan_router)
    app.include_router(dashboard_router)
    app.include_router(portfolios_router)
    app.include_router(trades_router)
    app.include_router(backtests_router)
    app.include_router(admin_router)
    app.include_router(auth_router)
    mount_frontend(app)

    @app.on_event("startup")
    def startup() -> None:
        validate_production_settings()
        Base.metadata.create_all(engine)
        ensure_sqlite_schema()
        with SessionLocal() as session:
            seed_default_owner(session, settings.default_owner_id)

    return app


def mount_frontend(app: FastAPI) -> None:
    if not settings.static_dir:
        return
    static_dir = Path(settings.static_dir)
    index_file = static_dir / "index.html"
    if static_dir.exists() and index_file.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")


app = create_app()


def ensure_sqlite_schema() -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        strategy_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(strategy_configs)"))
        }
        if "archived_at" not in strategy_columns:
            connection.execute(text("ALTER TABLE strategy_configs ADD COLUMN archived_at DATETIME"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS strategy_config_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_config_id INTEGER NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    memo VARCHAR(500),
                    strategy_type VARCHAR(100) NOT NULL,
                    symbol VARCHAR(32) NOT NULL,
                    fee_rate NUMERIC(18, 6) NOT NULL,
                    slippage_rate NUMERIC(18, 6) NOT NULL,
                    settings_json JSON NOT NULL,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY(strategy_config_id) REFERENCES strategy_configs (id)
                )
                """
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_strategy_config_snapshots_strategy_config_id "
                "ON strategy_config_snapshots (strategy_config_id)"
            )
        )
        snapshot_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(backtest_daily_snapshots)"))
        }
        if "mode" not in snapshot_columns:
            connection.execute(
                text(
                    "ALTER TABLE backtest_daily_snapshots "
                    "ADD COLUMN mode VARCHAR(10) NOT NULL DEFAULT 'safe'"
                )
            )
        if "mode_rule_code" not in snapshot_columns:
            connection.execute(
                text("ALTER TABLE backtest_daily_snapshots ADD COLUMN mode_rule_code VARCHAR(32)")
            )
        position_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(positions)"))
        }
        if "limit_price" not in position_columns:
            connection.execute(text("ALTER TABLE positions ADD COLUMN limit_price NUMERIC(18, 6)"))
        trade_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(trades)"))
        }
        if "limit_price" not in trade_columns:
            connection.execute(text("ALTER TABLE trades ADD COLUMN limit_price NUMERIC(18, 6)"))
        if "position_id" not in trade_columns:
            connection.execute(text("ALTER TABLE trades ADD COLUMN position_id INTEGER"))
        if "entry_date" not in trade_columns:
            connection.execute(text("ALTER TABLE trades ADD COLUMN entry_date DATE"))
        if "entry_price" not in trade_columns:
            connection.execute(text("ALTER TABLE trades ADD COLUMN entry_price NUMERIC(18, 6)"))
        backtest_trade_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(backtest_trades)"))
        }
        if "holding_days" not in backtest_trade_columns:
            connection.execute(text("ALTER TABLE backtest_trades ADD COLUMN holding_days INTEGER"))
        if "open_position_count" not in backtest_trade_columns:
            connection.execute(text("ALTER TABLE backtest_trades ADD COLUMN open_position_count INTEGER"))
        if "cash_after" not in backtest_trade_columns:
            connection.execute(text("ALTER TABLE backtest_trades ADD COLUMN cash_after NUMERIC(18, 6)"))
        if "capital_after" not in backtest_trade_columns:
            connection.execute(text("ALTER TABLE backtest_trades ADD COLUMN capital_after NUMERIC(18, 6)"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS portfolio_adjustments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_config_id INTEGER NOT NULL,
                    date DATE NOT NULL,
                    cash_delta NUMERIC(18, 6) NOT NULL,
                    capital_delta NUMERIC(18, 6) NOT NULL,
                    memo VARCHAR(500),
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY(strategy_config_id) REFERENCES strategy_configs (id)
                )
                """
            )
        )
        portfolio_adjustment_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(portfolio_adjustments)"))
        }
        if "source" not in portfolio_adjustment_columns:
            connection.execute(
                text("ALTER TABLE portfolio_adjustments ADD COLUMN source VARCHAR(64) NOT NULL DEFAULT 'manual'")
            )
        if "period_start_date" not in portfolio_adjustment_columns:
            connection.execute(text("ALTER TABLE portfolio_adjustments ADD COLUMN period_start_date DATE"))
        if "period_end_date" not in portfolio_adjustment_columns:
            connection.execute(text("ALTER TABLE portfolio_adjustments ADD COLUMN period_end_date DATE"))
        owner_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(owners)"))
        }
        if "pin_hash" not in owner_columns:
            connection.execute(text("ALTER TABLE owners ADD COLUMN pin_hash VARCHAR(255)"))
        if "is_active" not in owner_columns:
            connection.execute(text("ALTER TABLE owners ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"))
        if "is_admin" not in owner_columns:
            connection.execute(text("ALTER TABLE owners ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"))
        if "created_at" not in owner_columns:
            connection.execute(text("ALTER TABLE owners ADD COLUMN created_at DATETIME"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS loc_orders (
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
