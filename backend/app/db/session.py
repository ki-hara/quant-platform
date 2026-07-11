from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def create_engine_kwargs(database_url: str) -> dict:
    url = make_url(database_url)
    if url.get_backend_name().startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


def create_database_engine(database_url: str) -> Engine:
    database_engine = create_engine(database_url, **create_engine_kwargs(database_url))
    if make_url(database_url).get_backend_name().startswith("sqlite"):

        @event.listens_for(database_engine, "connect")
        def set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA busy_timeout=5000")
            finally:
                cursor.close()

    return database_engine


engine = create_database_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
