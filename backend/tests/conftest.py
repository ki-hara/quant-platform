from fastapi.testclient import TestClient

from app.main import create_app


def test_client() -> TestClient:
    return TestClient(create_app())
