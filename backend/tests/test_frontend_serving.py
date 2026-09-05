import pytest
from fastapi.testclient import TestClient
from backend.main import app


def test_frontend_static_serving():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "HPoker" in resp.text
    assert 'rel="manifest"' in resp.text
    assert 'apple-mobile-web-app-capable' in resp.text


def test_pwa_manifest_and_sw_serving():
    client = TestClient(app)

    # Web App Manifest
    manifest_resp = client.get("/manifest.webmanifest")
    assert manifest_resp.status_code == 200
    manifest = manifest_resp.json()
    assert manifest["short_name"] == "HPoker"
    assert manifest["display"] in ["standalone", "fullscreen"]
    assert len(manifest["icons"]) >= 4

    # Service Worker
    sw_resp = client.get("/sw.js")
    assert sw_resp.status_code == 200
    assert "addEventListener" in sw_resp.text
    assert "hpoker" in sw_resp.text.lower()

    # Favicon and Icons
    icon_resp = client.get("/icons/icon-192.png")
    assert icon_resp.status_code == 200
    assert icon_resp.content.startswith(b"\x89PNG")

    svg_resp = client.get("/favicon.svg")
    assert svg_resp.status_code == 200
    assert "<svg" in svg_resp.text

