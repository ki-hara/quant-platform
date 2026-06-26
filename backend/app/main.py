from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes_backtests import router as backtests_router
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_portfolios import router as portfolios_router
from app.api.routes_trading_plan import router as trading_plan_router
from app.api.routes_strategies import router as strategies_router
from app.api.routes_trades import router as trades_router
from app.core.config import settings
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

    @app.on_event("startup")
    def startup() -> None:
        Base.metadata.create_all(engine)
        ensure_sqlite_schema()
        with SessionLocal() as session:
            seed_default_owner(session, settings.default_owner_id)

    return app


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
