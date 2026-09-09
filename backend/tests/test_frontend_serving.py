import re
import pytest
from fastapi.testclient import TestClient
from backend.main import app


def test_unauthenticated_stealth_html_serving():
    """Verify that unauthenticated user loading HTML gets zero poker information."""
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200

    # Strict zero-leak assertion: no poker, texas, spade or chinese poker keywords
    lower_text = resp.text.lower()
    assert "hpoker" not in lower_text
    assert "poker" not in lower_text
    assert "德州" not in resp.text
    assert "扑克" not in resp.text
    assert "♠" not in resp.text
    assert "texas" not in lower_text
    assert "holdem" not in lower_text
    assert "现金局" not in resp.text

    # Neutral portal tags
    assert "<title>系统登录</title>" in resp.text
    assert 'rel="manifest"' in resp.text
    assert "apple-mobile-web-app-capable" in resp.text


def test_pwa_manifest_and_sw_serving():
    """Verify that Web App Manifest and Service Worker are completely neutralized."""
    client = TestClient(app)

    # Web App Manifest
    manifest_resp = client.get("/manifest.webmanifest")
    assert manifest_resp.status_code == 200
    manifest = manifest_resp.json()
    assert manifest["short_name"] == "Portal"
    assert "poker" not in manifest["name"].lower()
    assert "德州" not in manifest["name"]
    assert "games" not in manifest.get("categories", [])
    assert manifest["display"] in ["standalone", "fullscreen"]
    assert len(manifest["icons"]) >= 4

    # Service Worker
    sw_resp = client.get("/sw.js")
    assert sw_resp.status_code == 200
    assert "addEventListener" in sw_resp.text
    assert "hpoker" not in sw_resp.text.lower()
    assert "德州" not in sw_resp.text

    # Favicon and Icons
    icon_resp = client.get("/icons/icon-192.png")
    assert icon_resp.status_code == 200
    assert icon_resp.content.startswith(b"\x89PNG")

    svg_resp = client.get("/favicon.svg")
    assert svg_resp.status_code == 200
    assert "<svg" in svg_resp.text
    assert "spade" not in svg_resp.text.lower()


def test_public_api_docs_hidden():
    """Verify that Swagger UI and OpenAPI schemas are disabled to prevent detection."""
    client = TestClient(app)
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_unauthenticated_entry_js_zero_poker_footprint():
    """Verify that entry JS loaded before login contains no poker keywords (via code-splitting)."""
    client = TestClient(app)
    html_resp = client.get("/")
    assert html_resp.status_code == 200

    # Extract entry JS path from script tag: <script type="module" crossorigin src="/assets/index-xxx.js"></script>
    match = re.search(r'src="(/assets/index-[^"]+\.js)"', html_resp.text)
    if match:
        js_path = match.group(1)
        js_resp = client.get(js_path)
        assert js_resp.status_code == 200
        js_text = js_resp.text
        lower_js = js_text.lower()

        # Strict assertion on unauthenticated entry JS bundle
        assert "hpoker" not in lower_js
        assert "poker" not in lower_js
        assert "德州" not in js_text
        assert "扑克" not in js_text
        assert "♠" not in js_text
        assert "texas" not in lower_js
        assert "holdem" not in lower_js
        assert "all-in" not in lower_js
        assert "盲注" not in js_text
        assert "底池" not in js_text
        assert "筹码" not in js_text


