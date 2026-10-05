from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes_settlements import router
from app.core.security import create_owner_token
from app.db.base import Base
from app.db.seed import seed_default_owner
from app.db.session import get_session
from tests.test_settlement_service import prepare


def settlement_app():
    engine = create_engine("sqlite://", connect_args={"check_same_thread":False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_default_owner(session, "default")
        config, record, service = prepare(session)
        config_id, record_id = config.id, record.id
    def sessions():
        with Session(engine) as session:
            yield session
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = sessions
    return app, config_id, record_id, engine


def test_http_save_preview_confirm_retry_and_cancel():
    app, config_id, record_id, engine = settlement_app()
    base = f"/api/strategy-configs/{config_id}"
    client = TestClient(app)
    assert client.get(base+"/settlements").status_code == 401
    client.headers["Authorization"] = "Bearer "+create_owner_token("default")
    rows = client.get(base+"/settlements").json()
    assert rows[0]["status"] == "draft"
    preview = client.post(f"{base}/settlements/{record_id}/preview")
    assert preview.status_code == 200
    body = dict(preview_hash=preview.json()["preview_hash"], idempotency_key="http")
    result = client.post(f"{base}/settlements/{record_id}/confirm", json=body)
    assert result.status_code == 200, result.text
    assert result.json()["cash_delta"] == "549"
    retry = client.post(f"{base}/settlements/{record_id}/confirm", json=body)
    assert retry.json() == result.json()
    assert client.put(f"{base}/settlements/{record_id}/draft", json={
        "expected_revision":rows[0]["revision"], "draft":rows[0]["draft"]}).status_code == 422
    assert client.post(f"{base}/settlements/{record_id}/cancel").status_code == 200
    Base.metadata.create_all(engine)
    assert "trade_settlements" in inspect(engine).get_table_names()


def test_bad_date_and_snapshot_scope_and_context_json():
    app, config_id, _, _ = settlement_app()
    client = TestClient(app, headers={"Authorization":"Bearer "+create_owner_token("default")})
    base = f"/api/strategy-configs/{config_id}"
    result = client.get(base+"/settlement-context?trade_date=2026-09-24")
    assert result.status_code == 200, result.text
    assert result.json()["sources"][0]["side"] == "sell"
    assert client.get(base+"/settlement-context?trade_date=2026-09-24&snapshot_id=999").status_code == 422
    assert client.get(base+"/settlement-context?trade_date=bad").status_code == 422
