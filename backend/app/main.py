from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine
from sqlalchemy.orm import Session

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
from app.db.migrations import run_sqlite_migrations
from app.db.seed import seed_default_owner
from app.db.session import SessionLocal, engine


def create_app(
    database_engine: Engine = engine,
    session_factory: Callable[[], Session] = SessionLocal,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        validate_production_settings()
        Base.metadata.create_all(database_engine)
        run_sqlite_migrations(database_engine)
        with session_factory() as session:
            seed_default_owner(session, settings.default_owner_id)
        yield

    app = FastAPI(title="Quant Strategy Platform", version="0.1.0", lifespan=lifespan)
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

    return app


def mount_frontend(app: FastAPI) -> None:
    if not settings.static_dir:
        return
    static_dir = Path(settings.static_dir)
    index_file = static_dir / "index.html"
    if static_dir.exists() and index_file.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")


app = create_app()
