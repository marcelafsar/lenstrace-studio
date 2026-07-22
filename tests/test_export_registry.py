"""Tests for the export registry security boundary."""

from __future__ import annotations

import pytest

from backend.services.export_registry import ExportRegistry
from core.delivery.exceptions import UnknownExportError


def test_register_and_resolve(sample_jpeg):
    reg = ExportRegistry()
    export_id = reg.register(sample_jpeg)
    assert reg.resolve(export_id) == sample_jpeg.resolve()


def test_unknown_id_rejected():
    reg = ExportRegistry()
    with pytest.raises(UnknownExportError):
        reg.resolve("nope")


def test_directory_rejected(tmp_path):
    reg = ExportRegistry()
    with pytest.raises(ValueError):
        reg.register(tmp_path)


def test_missing_file_rejected(tmp_path):
    reg = ExportRegistry()
    with pytest.raises(ValueError):
        reg.register(tmp_path / "missing.jpg")


def test_path_outside_approved_dirs_rejected(sample_jpeg, tmp_path):
    reg = ExportRegistry()
    # Seed an approved dir that does NOT contain the sample file.
    approved = tmp_path / "approved"
    approved.mkdir()
    reg.approve_directory(approved)
    with pytest.raises(ValueError):
        reg.register(sample_jpeg)


def test_resolve_after_file_deleted(sample_jpeg):
    reg = ExportRegistry()
    export_id = reg.register(sample_jpeg)
    sample_jpeg.unlink()
    with pytest.raises(UnknownExportError):
        reg.resolve(export_id)


def test_expiry(sample_jpeg):
    reg = ExportRegistry(ttl_seconds=0)
    export_id = reg.register(sample_jpeg)
    # With a zero TTL the entry expires immediately.
    with pytest.raises(UnknownExportError):
        reg.resolve(export_id)


def test_info_roundtrip(sample_jpeg):
    from core.delivery.metadata_verification import build_export_info

    reg = ExportRegistry()
    info = build_export_info(sample_jpeg)
    export_id = reg.register(sample_jpeg, info)
    assert reg.get_info(export_id).sha256 == info.sha256
