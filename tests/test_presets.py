"""Tests for preset loading and schema validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.exceptions import InvalidPresetError
from core.presets.loader import PresetLoader, get_default_loader
from core.presets.schema import PresetLibrary


def test_bundled_presets_load():
    loader = get_default_loader()
    devices = loader.list_devices()
    assert len(devices) > 10
    # Generic fallback is always present.
    assert loader.get("generic-apple-iphone").exif_model == "iPhone"


def test_known_preset_values():
    loader = get_default_loader()
    device = loader.get("iphone-13-pro")
    assert device.exif_model == "iPhone 13 Pro"
    assert any(lens.id == "telephoto" for lens in device.lenses)


def test_grouped_by_generation():
    groups = get_default_loader().grouped_by_generation()
    assert "iPhone 13" in groups
    assert all(isinstance(v, list) for v in groups.values())


def test_duplicate_device_id_rejected():
    raw = {
        "schema_version": 1,
        "devices": [
            {"id": "dup", "manufacturer": "Apple", "display_name": "A", "exif_model": "A"},
            {"id": "dup", "manufacturer": "Apple", "display_name": "B", "exif_model": "B"},
        ],
    }
    with pytest.raises(ValidationError):
        PresetLibrary.model_validate(raw)


def test_duplicate_lens_id_rejected():
    raw = {
        "schema_version": 1,
        "devices": [
            {
                "id": "x",
                "manufacturer": "Apple",
                "display_name": "X",
                "exif_model": "X",
                "lenses": [
                    {"id": "main", "display_name": "Main"},
                    {"id": "main", "display_name": "Main 2"},
                ],
            }
        ],
    }
    with pytest.raises(ValidationError):
        PresetLibrary.model_validate(raw)


def test_malformed_fnumber_rejected():
    raw = {
        "schema_version": 1,
        "devices": [
            {
                "id": "x",
                "manufacturer": "Apple",
                "display_name": "X",
                "exif_model": "X",
                "lenses": [{"id": "main", "display_name": "Main", "f_number": -1}],
            }
        ],
    }
    with pytest.raises(ValidationError):
        PresetLibrary.model_validate(raw)


def test_missing_file_raises(tmp_path):
    loader = PresetLoader(tmp_path / "does_not_exist.json")
    with pytest.raises(InvalidPresetError):
        loader.load()


def test_bad_json_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    with pytest.raises(InvalidPresetError):
        PresetLoader(bad).load()


def test_every_bundled_source_status_declared():
    loader = get_default_loader()
    for device in loader.list_devices():
        # Placeholder vs verified must be explicit for every device.
        assert device.source_status.value in {"verified", "placeholder", "generic", "custom"}
