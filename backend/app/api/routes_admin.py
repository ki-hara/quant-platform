from datetime import datetime
from pathlib import Path
import sqlite3
import tempfile

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.engine import make_url
from starlette.background import BackgroundTask

from app.api.deps import CurrentOwnerDep
from app.core.config import settings


router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/sqlite-backup")
def download_sqlite_backup(owner: CurrentOwnerDep) -> FileResponse:
    _ = owner
    url = make_url(settings.database_url)
    if not url.get_backend_name().startswith("sqlite") or not url.database:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SQLite database backup is only available when SQLite is configured.",
        )
    if url.database == ":memory:":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="In-memory SQLite databases cannot be downloaded.",
        )

    source_path = Path(url.database).expanduser()
    if not source_path.is_absolute():
        source_path = Path.cwd() / source_path
    source_path = source_path.resolve()
    if not source_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SQLite database file not found: {source_path}",
        )

    backup_path = _create_sqlite_backup(source_path)
    filename = f"quant-platform-backup-{datetime.utcnow():%Y%m%d-%H%M%S}.db"
    return FileResponse(
        backup_path,
        media_type="application/octet-stream",
        filename=filename,
        background=BackgroundTask(lambda: backup_path.unlink(missing_ok=True)),
    )


def _create_sqlite_backup(source_path: Path) -> Path:
    temp_file = tempfile.NamedTemporaryFile(prefix="quant-platform-", suffix=".db", delete=False)
    temp_file.close()
    backup_path = Path(temp_file.name)
    try:
        with sqlite3.connect(source_path) as source, sqlite3.connect(backup_path) as destination:
            source.backup(destination)
    except Exception:
        backup_path.unlink(missing_ok=True)
        raise
    return backup_path
