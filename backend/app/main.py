from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_backtests import router as backtests_router
from app.api.routes_dashboard import router as dashboard_router
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
    app.include_router(trades_router)
    app.include_router(backtests_router)

    @app.on_event("startup")
    def startup() -> None:
        Base.metadata.create_all(engine)
        with SessionLocal() as session:
            seed_default_owner(session, settings.default_owner_id)

    return app


app = create_app()
