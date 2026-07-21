"""Tests for the three delivery providers (iCloud, PairDrop, Apple Devices)."""

from __future__ import annotations

import pytest

from backend.services import settings_service
from backend.services.apple_devices_service import AppleDevicesProvider
from backend.services.icloud_photos_service import ICloudPhotosProvider
from backend.services.pairdrop_service import (
    PairDropProvider,
    build_cli_command,
    resolve_url,
)
from core.delivery.checksums import files_match
from core.delivery.models import AvailabilityLevel, DeliveryOptions, DeliveryState


def _reload(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    settings_service.reload_config()


# ---- iCloud --------------------------------------------------------------


def test_icloud_available_when_folder_configured(isolated_state, tmp_path, monkeypatch):
    folder = tmp_path / "iCloud Photos"
    folder.mkdir()
    _reload(monkeypatch, ICLOUD_PHOTOS_PATH=str(folder))
    avail = ICloudPhotosProvider().availability()
    assert avail.level == AvailabilityLevel.READY
    assert avail.recommended


def test_icloud_needs_setup_when_no_folder(isolated_state, tmp_path, monkeypatch):
    _reload(monkeypatch, ICLOUD_PHOTOS_PATH=str(tmp_path / "missing"))
    avail = ICloudPhotosProvider().availability()
    assert avail.level == AvailabilityLevel.NEEDS_SETUP


def test_icloud_execute_copies_and_verifies(isolated_state, sample_jpeg, tmp_path, monkeypatch):
    folder = tmp_path / "iCloud Photos"
    folder.mkdir()
    _reload(monkeypatch, ICLOUD_PHOTOS_PATH=str(folder))
    from core.delivery.metadata_verification import build_export_info

    provider = ICloudPhotosProvider()
    result = provider.execute(sample_jpeg, build_export_info(sample_jpeg), DeliveryOptions())
    assert result.state == DeliveryState.WAITING_FOR_SYNC
    assert result.destination_verified
    copied = folder / sample_jpeg.name
    assert copied.exists() and files_match(sample_jpeg, copied)


def test_icloud_execute_collision(isolated_state, sample_jpeg, tmp_path, monkeypatch):
    folder = tmp_path / "iCloud Photos"
    folder.mkdir()
    _reload(monkeypatch, ICLOUD_PHOTOS_PATH=str(folder))
    from core.delivery.metadata_verification import build_export_info

    provider = ICloudPhotosProvider()
    info = build_export_info(sample_jpeg)
    provider.execute(sample_jpeg, info, DeliveryOptions())
    second = provider.execute(sample_jpeg, info, DeliveryOptions())
    assert "(1)" in second.destination_name


# ---- PairDrop ------------------------------------------------------------


def test_pairdrop_ready(isolated_state, monkeypatch):
    _reload(monkeypatch, PAIRDROP_ENABLED="true")
    assert PairDropProvider().availability().level == AvailabilityLevel.READY


def test_pairdrop_prepare_qr_is_url_only(isolated_state, sample_jpeg, monkeypatch):
    _reload(monkeypatch, PAIRDROP_URL="https://pairdrop.net/")
    from core.delivery.metadata_verification import build_export_info

    prep = PairDropProvider().prepare(
        sample_jpeg, build_export_info(sample_jpeg), DeliveryOptions()
    )
    url = prep.user_action.open_url
    # The QR/open payload is exactly the validated URL — no path, token, or metadata.
    assert url == "https://pairdrop.net/"
    assert str(sample_jpeg) not in url


def test_pairdrop_rejects_dangerous_custom_url(isolated_state, monkeypatch):
    from core.delivery.exceptions import UnsafeUrlError

    _reload(monkeypatch)
    with pytest.raises(UnsafeUrlError):
        resolve_url(DeliveryOptions(extra={"pairdrop_url": "javascript:alert(1)"}))


def test_pairdrop_custom_https_instance(isolated_state, monkeypatch):
    _reload(monkeypatch)
    url = resolve_url(DeliveryOptions(extra={"pairdrop_url": "https://drop.example.org/"}))
    assert url == "https://drop.example.org/"


def test_pairdrop_execute_is_not_completed(isolated_state, sample_jpeg, monkeypatch):
    _reload(monkeypatch)
    from core.delivery.metadata_verification import build_export_info

    result = PairDropProvider().execute(
        sample_jpeg, build_export_info(sample_jpeg), DeliveryOptions()
    )
    # Opening a browser is never "completed".
    assert result.state == DeliveryState.AWAITING_USER


def test_pairdrop_cli_command_is_safe_argv(tmp_path):
    cli = tmp_path / "pairdrop"
    cli.write_text("#!/bin/sh\n", encoding="utf-8")
    f = tmp_path / "my photo.jpg"
    f.write_bytes(b"x")
    cmd = build_cli_command(str(cli), f)
    assert isinstance(cmd, list)
    assert cmd == [str(cli), str(f)]  # spaces handled by the OS, never a shell


def test_pairdrop_cli_not_found(isolated_state, monkeypatch):
    _reload(monkeypatch, PAIRDROP_CLI_PATH="/definitely/not/here/pairdrop")
    monkeypatch.setattr("shutil.which", lambda name: None)
    from backend.services.pairdrop_service import detect_cli

    assert detect_cli() is None


# ---- Apple Devices -------------------------------------------------------


def test_apple_devices_ready(isolated_state, tmp_path, monkeypatch):
    _reload(monkeypatch, LENSTRACE_SYNC_PATH=str(tmp_path / "sync"))
    assert AppleDevicesProvider().availability().level == AvailabilityLevel.READY


def test_apple_devices_execute_copies_verified(isolated_state, sample_jpeg, tmp_path, monkeypatch):
    sync = tmp_path / "sync"
    _reload(monkeypatch, LENSTRACE_SYNC_PATH=str(sync))
    from core.delivery.metadata_verification import build_export_info

    result = AppleDevicesProvider().execute(
        sample_jpeg, build_export_info(sample_jpeg), DeliveryOptions()
    )
    assert result.state == DeliveryState.WAITING_FOR_SYNC
    assert result.destination_verified
    assert result.user_action.open_app == "apple_devices"
    assert (sync / sample_jpeg.name).exists()


def test_apple_devices_unavailable_when_disabled(isolated_state, monkeypatch):
    _reload(monkeypatch, APPLE_DEVICES_ENABLED="false")
    assert AppleDevicesProvider().availability().level == AvailabilityLevel.UNAVAILABLE
