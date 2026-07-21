"""API-level tests for the delivery, bots, and config endpoints."""

from __future__ import annotations

import io

import piexif
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.config import get_settings

_TOKEN = "api-test-token"


@pytest.fixture
def client(tmp_path, monkeypatch, isolated_state):
    monkeypatch.setenv("LENSTRACE_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("LENSTRACE_SESSION_TOKEN", _TOKEN)
    monkeypatch.setenv("LENSTRACE_DEFAULT_OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("LENSTRACE_SYNC_PATH", str(tmp_path / "sync"))
    import backend.config as config

    config._settings = None
    get_settings()
    from backend.services import secrets_service, settings_service

    monkeypatch.setattr(secrets_service, "_KEYRING_AVAILABLE", False)
    settings_service.reload_config()
    from backend.main import create_app

    return TestClient(create_app())


def _auth():
    return {"X-LensTrace-Token": _TOKEN}


def _jpeg() -> bytes:
    img = Image.new("RGB", (24, 24), (5, 5, 5))
    exif = {
        "0th": {piexif.ImageIFD.Make: b"Apple"},
        "Exif": {},
        "GPS": {},
        "1st": {},
        "Interop": {},
        "thumbnail": None,
    }
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=piexif.dump(exif))
    return buf.getvalue()


def _export_id(client) -> str:
    up = client.post(
        "/files/upload", headers=_auth(), files={"file": ("p.jpg", _jpeg(), "image/jpeg")}
    )
    fid = up.json()["file_id"]
    exp = client.post(
        "/metadata/export", headers=_auth(), json={"file_id": fid, "preset_id": "iphone-15"}
    )
    return exp.json()["export_id"]


# ---- Auth ----------------------------------------------------------------


@pytest.mark.parametrize("path", ["/delivery/providers", "/bots", "/config/status"])
def test_new_routes_require_token(client, path):
    assert client.get(path).status_code == 401


# ---- Delivery ------------------------------------------------------------


def test_providers_list(client):
    resp = client.get("/delivery/providers", headers=_auth())
    assert resp.status_code == 200
    ids = {p["provider_id"] for p in resp.json()["providers"]}
    assert ids == {"icloud_photos", "pairdrop", "apple_devices"}


def test_apple_devices_prepare_execute_flow(client):
    eid = _export_id(client)
    prep = client.post(
        "/delivery/apple_devices/prepare", headers=_auth(), json={"export_id": eid, "options": {}}
    )
    assert prep.status_code == 200
    job_id = prep.json()["job_id"]
    ex = client.post(f"/delivery/jobs/{job_id}/execute", headers=_auth())
    body = ex.json()
    assert body["state"] == "waiting_for_sync"
    assert body["destination_verified"] is True


def test_pairdrop_execute_not_completed(client):
    eid = _export_id(client)
    prep = client.post(
        "/delivery/pairdrop/prepare", headers=_auth(), json={"export_id": eid, "options": {}}
    )
    job_id = prep.json()["job_id"]
    ex = client.post(f"/delivery/jobs/{job_id}/execute", headers=_auth())
    assert ex.json()["state"] == "awaiting_user"
    assert ex.json()["completed"] is False


def test_delivery_rejects_unknown_export(client):
    resp = client.post(
        "/delivery/apple_devices/prepare",
        headers=_auth(),
        json={"export_id": "nope", "options": {}},
    )
    assert resp.status_code == 404


def test_validate_url_endpoint(client):
    good = client.post(
        "/delivery/validate-url", headers=_auth(), json={"url": "https://pairdrop.net/"}
    )
    assert good.json()["valid"] and good.json()["is_default"]
    bad = client.post("/delivery/validate-url", headers=_auth(), json={"url": "javascript:x"})
    assert bad.json()["valid"] is False


# ---- Bots ----------------------------------------------------------------


def test_bots_list_unconfigured(client):
    resp = client.get("/bots", headers=_auth())
    assert resp.status_code == 200
    kinds = {b["kind"]: b for b in resp.json()["bots"]}
    assert kinds["telegram"]["token_configured"] is False
    assert kinds["telegram"]["runtime"]["state"] == "not_configured"


def test_save_token_never_returns_secret(client):
    fake = "123456:ABCDEF_secret_never_returned_00000000"
    resp = client.post("/bots/telegram/token", headers=_auth(), json={"token": fake})
    assert resp.status_code == 200
    assert fake not in resp.text
    assert resp.json()["token_configured"] is True
    assert resp.json()["token_masked_suffix"]


def test_start_disabled_until_configured(client):
    resp = client.post("/bots/telegram/start", headers=_auth())
    assert resp.status_code == 400  # no token yet


def test_clear_token(client):
    fake = "123456:ABCDEF_secret_0000000000000000000000"
    client.post("/bots/telegram/token", headers=_auth(), json={"token": fake})
    resp = client.delete("/bots/telegram/secret", headers=_auth())
    assert resp.json()["token_configured"] is False


def test_update_bot_settings(client):
    resp = client.put("/bots/discord/settings", headers=_auth(), json={"auto_start": True})
    assert resp.json()["auto_start"] is True


# ---- Config --------------------------------------------------------------


def test_config_status(client):
    resp = client.get("/config/status", headers=_auth())
    assert resp.status_code == 200
    report = resp.json()["report"]
    assert report["passed"] > 0
    assert "results" in report
