"""Tests for the local FastAPI backend using an in-process test client."""

from __future__ import annotations

import io

import piexif
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.config import get_settings
from backend.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Isolate the work dir and pin a known token per test run.
    monkeypatch.setenv("LENSTRACE_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("LENSTRACE_SESSION_TOKEN", "test-token-123")
    monkeypatch.setenv("LENSTRACE_DEFAULT_OUTPUT_DIR", str(tmp_path / "out"))
    # Reset the settings singleton so env vars take effect.
    import backend.config as config

    config._settings = None
    get_settings()
    return TestClient(create_app())


def _auth():
    return {"X-LensTrace-Token": "test-token-123"}


def _jpeg_bytes() -> bytes:
    img = Image.new("RGB", (32, 24), (120, 130, 140))
    exif = {
        "0th": {piexif.ImageIFD.Make: b"OldMake", piexif.ImageIFD.Model: b"OldModel"},
        "Exif": {},
        "GPS": {},
        "1st": {},
        "Interop": {},
        "thumbnail": None,
    }
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=piexif.dump(exif))
    return buf.getvalue()


def test_health_is_unauthenticated(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_presets_requires_token(client):
    assert client.get("/presets").status_code == 401


def test_presets_with_token(client):
    resp = client.get("/presets", headers=_auth())
    assert resp.status_code == 200
    body = resp.json()
    assert any(d["id"] == "iphone-13-pro" for d in body["devices"])


def test_upload_inspect_preview_export_flow(client):
    # Upload
    resp = client.post(
        "/files/upload",
        headers=_auth(),
        files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert resp.status_code == 200, resp.text
    file_id = resp.json()["file_id"]
    assert resp.json()["image_format"] == "JPEG"

    # Inspect
    resp = client.get(f"/files/{file_id}/inspect", headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["summary"]["make"] == "OldMake"

    # Preview
    change = {"file_id": file_id, "preset_id": "iphone-13-pro", "lens_id": "main"}
    resp = client.post("/metadata/preview", headers=_auth(), json=change)
    assert resp.status_code == 200
    fields = {r["field"]: r for r in resp.json()["diff"]["rows"]}
    assert fields["Model"]["new"] == "iPhone 13 Pro"
    assert "does not prove" in resp.json()["disclaimer"]

    # Export
    resp = client.post("/metadata/export", headers=_auth(), json=change)
    assert resp.status_code == 200
    assert resp.json()["result"]["success"] is True


def test_upload_rejects_non_image(client):
    resp = client.post(
        "/files/upload",
        headers=_auth(),
        files={"file": ("notimage.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 400


def test_bad_file_id_preview(client):
    resp = client.post(
        "/metadata/preview",
        headers=_auth(),
        json={"file_id": "does-not-exist", "preset_id": "iphone-15"},
    )
    assert resp.status_code == 400


@pytest.mark.parametrize(
    "origin",
    [
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",  # Vite falls back to this if 5173 is taken.
        "http://localhost:5199",
        "http://localhost:41235",
    ],
)
def test_cors_allows_any_loopback_port(client, origin):
    # Regression test: CORS must not be hardcoded to port 5173, since Vite's
    # strictPort: false means it may bind to a different port when 5173 is
    # already in use by another project.
    resp = client.get("/health", headers={"Origin": origin})
    assert resp.headers.get("access-control-allow-origin") == origin


def test_cors_rejects_non_loopback_origin(client):
    resp = client.get("/health", headers={"Origin": "http://evil.example.com"})
    assert "access-control-allow-origin" not in {k.lower() for k in resp.headers}
