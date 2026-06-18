from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

    @app.on_event("startup")
    def startup() -> None:
        Base.metadata.create_all(engine)
        with SessionLocal() as session:
            seed_default_owner(session, settings.default_owner_id)

    return app


app = create_app()
