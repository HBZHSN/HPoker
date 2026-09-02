import pytest
from fastapi.testclient import TestClient
from backend.main import app


def test_frontend_static_serving():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "HPoker" in resp.text
