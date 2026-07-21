"""End-to-end tests for the metadata engine on JPEG images."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import piexif
import pytest

from core.exceptions import CorruptImageError
from core.metadata_models import DateStrategy, GPSData
from core.metadata_reader import read_summary


def _exif_model(path: Path) -> str | None:
    data = piexif.load(str(path))
    raw = data["0th"].get(piexif.ImageIFD.Model)
    return raw.decode() if raw else None


def test_inspect_reads_original(engine, sample_jpeg):
    summary = engine.inspect_image(sample_jpeg)
    assert summary.make == "OldMake"
    assert summary.model == "OldModel"
    assert summary.datetime_original == "2020:01:01 08:00:00"


def test_apply_preset_writes_model(engine, sample_jpeg, output_dir):
    plan = engine.build_change_plan(
        sample_jpeg, output_dir, preset_id="iphone-13-pro", lens_id="main"
    )
    result = engine.apply_metadata(plan)
    assert result.success
    assert _exif_model(result.destination_path) == "iPhone 13 Pro"


def test_original_is_not_modified(engine, sample_jpeg, output_dir):
    before = sample_jpeg.read_bytes()
    plan = engine.build_change_plan(sample_jpeg, output_dir, preset_id="iphone-15-pro")
    engine.apply_metadata(plan)
    assert sample_jpeg.read_bytes() == before


def test_set_datetime_and_offset(engine, sample_jpeg, output_dir):
    plan = engine.build_change_plan(
        sample_jpeg,
        output_dir,
        date_strategy=DateStrategy.SET_EXPLICIT,
        datetime_original=datetime(2026, 7, 21, 16, 45, 0),
        utc_offset="+02:00",
        timezone_name="Europe/Istanbul",
    )
    result = engine.apply_metadata(plan)
    written = read_summary(result.destination_path)
    assert written.datetime_original == "2026:07:21 16:45:00"
    assert written.offset_time_original == "+02:00"


def test_set_gps(engine, sample_jpeg, output_dir):
    plan = engine.build_change_plan(
        sample_jpeg,
        output_dir,
        gps=GPSData(latitude=41.0082, longitude=28.9784, altitude_m=40.0),
    )
    result = engine.apply_metadata(plan)
    written = read_summary(result.destination_path)
    assert written.has_gps
    assert written.gps_latitude == pytest.approx(41.0082, abs=1e-4)
    assert written.gps_longitude == pytest.approx(28.9784, abs=1e-4)


def test_remove_metadata(engine, sample_jpeg, output_dir):
    result = engine.remove_metadata(sample_jpeg, output_dir)
    written = read_summary(result.destination_path)
    assert written.make is None
    assert written.model is None


def test_audit_sidecar_created(engine, sample_jpeg, output_dir):
    plan = engine.build_change_plan(
        sample_jpeg, output_dir, preset_id="iphone-14-pro", write_audit_sidecar=True
    )
    result = engine.apply_metadata(plan)
    assert result.audit_sidecar_path is not None
    assert result.audit_sidecar_path.exists()
    text = result.audit_sidecar_path.read_text(encoding="utf-8")
    assert "does NOT prove" in text


def test_diff_marks_added_and_changed(engine, sample_jpeg, output_dir):
    plan = engine.build_change_plan(sample_jpeg, output_dir, preset_id="iphone-13-pro")
    diff = engine.build_diff(plan)
    statuses = {row.field: row.status for row in diff.rows}
    assert statuses["Model"] == "changed"  # OldModel -> iPhone 13 Pro


def test_png_conversion_to_jpeg(engine, png_image, output_dir):
    plan = engine.build_change_plan(png_image, output_dir, preset_id="iphone-15")
    result = engine.apply_metadata(plan)
    assert result.converted_to_jpeg
    assert result.destination_path.suffix == ".jpg"
    assert any("JPEG" in w for w in result.warnings)


def test_unsupported_format_raises(engine, tmp_path, output_dir):
    fake = tmp_path / "notimage.txt"
    fake.write_text("hello", encoding="utf-8")
    with pytest.raises(CorruptImageError):
        # inspect_image (called during planning) rejects non-images.
        engine.build_change_plan(fake, output_dir, preset_id="iphone-15")
