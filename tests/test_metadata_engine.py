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


# ---- Resolution is never silently downscaled --------------------------------


def test_full_resolution_source_stays_full_resolution(engine, large_jpeg, output_dir):
    plan = engine.build_change_plan(
        large_jpeg, output_dir, preset_id="iphone-13-pro-max", lens_id="main"
    )
    result = engine.apply_metadata(plan)
    assert result.success
    written = read_summary(result.destination_path)
    assert (written.width, written.height) == (3024, 4032)
    assert result.verification.dimensions_ok


def test_low_resolution_source_not_upscaled(engine, sample_jpeg, output_dir):
    # sample_jpeg is a tiny 48x32 fixture; the export must not inflate it.
    plan = engine.build_change_plan(sample_jpeg, output_dir, preset_id="iphone-13-pro-max")
    result = engine.apply_metadata(plan)
    written = read_summary(result.destination_path)
    assert (written.width, written.height) == (48, 32)


def test_verification_detects_dimension_mismatch(engine, sample_jpeg, output_dir):
    plan = engine.build_change_plan(sample_jpeg, output_dir, preset_id="iphone-13-pro-max")
    # Simulate a plan whose recorded "original" resolution doesn't match the
    # actual exported file (the scenario the dimension guard exists to catch).
    tampered = plan.model_copy(
        update={"original_summary": plan.original_summary.model_copy(update={"width": 9999})}
    )
    verification = engine.verify_exported_metadata(sample_jpeg, tampered)
    assert verification.dimensions_ok is False
    assert verification.ok is False


def test_png_conversion_preserves_dimensions(engine, output_dir, tmp_path):
    from PIL import Image

    path = tmp_path / "big.png"
    Image.new("RGB", (1200, 800), color=(5, 5, 5)).save(path, format="PNG")
    plan = engine.build_change_plan(path, output_dir, preset_id="iphone-15")
    result = engine.apply_metadata(plan)
    written = read_summary(result.destination_path)
    assert (written.width, written.height) == (1200, 800)


# ---- Exposure fields: preserved by default, never invented ------------------


def _jpeg_with_exposure(path, *, iso=200, shutter=(1, 500), bias=(0, 1)) -> Path:
    import piexif
    from PIL import Image

    exif = {
        "0th": {piexif.ImageIFD.Make: b"OldMake"},
        "Exif": {
            piexif.ExifIFD.ISOSpeedRatings: iso,
            piexif.ExifIFD.ExposureTime: shutter,
            piexif.ExifIFD.ExposureBiasValue: bias,
        },
        "GPS": {},
        "1st": {},
        "Interop": {},
        "thumbnail": None,
    }
    Image.new("RGB", (48, 32), (1, 2, 3)).save(path, format="JPEG", exif=piexif.dump(exif))
    return path


def test_exposure_preserved_by_default(engine, tmp_path, output_dir):
    src = _jpeg_with_exposure(tmp_path / "exposed.jpg")
    plan = engine.build_change_plan(src, output_dir, preset_id="iphone-13-pro-max", lens_id="main")
    result = engine.apply_metadata(plan)
    written = read_summary(result.destination_path)
    assert written.iso == 200
    assert written.exposure_time == "1/500"
    assert written.exposure_bias == "0"
    assert result.verification.ok


def test_exposure_not_invented_when_autofill_disabled(engine, sample_jpeg, output_dir):
    # With auto-fill off and preserve mode, a preset must not add exposure data.
    plan = engine.build_change_plan(
        sample_jpeg, output_dir, preset_id="iphone-13-pro-max", auto_fill_exposure=False
    )
    result = engine.apply_metadata(plan)
    written = read_summary(result.destination_path)
    assert written.iso is None
    assert written.exposure_time is None
    assert written.exposure_bias is None


def test_explicit_exposure_written_and_verified(engine, sample_jpeg, output_dir):
    plan = engine.build_change_plan(
        sample_jpeg,
        output_dir,
        set_exposure=True,
        photographic_sensitivity=800,
        exposure_time=1 / 1000,
        exposure_bias=-0.7,
    )
    result = engine.apply_metadata(plan)
    written = read_summary(result.destination_path)
    assert written.iso == 800
    assert written.exposure_time == "1/1000"
    assert result.verification.ok
    fields = {f.field: f.ok for f in result.verification.fields}
    assert fields["ISO"] is True
    assert fields["ExposureTime"] is True
    assert fields["ExposureBiasValue"] is True


def test_explicit_exposure_overrides_existing(engine, tmp_path, output_dir):
    src = _jpeg_with_exposure(tmp_path / "exposed.jpg", iso=100)
    plan = engine.build_change_plan(
        src, output_dir, set_exposure=True, photographic_sensitivity=3200
    )
    result = engine.apply_metadata(plan)
    written = read_summary(result.destination_path)
    assert written.iso == 3200


# ---- HEIF source: the reported bug's exact scenario --------------------------
# Regression coverage for the reported defect: a genuine iPhone 13 Pro Max HEIC
# (12 MP, ISO/shutter/EV set) converting to JPEG must keep its full resolution
# and its existing exposure data, and gain the verified Wide Camera optical
# fields — not the previous 1 MP / blank-exposure / generic-ultrawide result.


@pytest.fixture
def large_heic(tmp_path: Path):
    pillow_heif = pytest.importorskip("pillow_heif")
    import piexif
    from PIL import Image

    pillow_heif.register_heif_opener()
    path = tmp_path / "iphone.heic"
    exif = {
        "0th": {piexif.ImageIFD.Make: b"Apple", piexif.ImageIFD.Model: b"iPhone 13 Pro Max"},
        "Exif": {
            piexif.ExifIFD.ISOSpeedRatings: 125,
            piexif.ExifIFD.ExposureTime: (1, 121),
            piexif.ExifIFD.FNumber: (150, 100),
            piexif.ExifIFD.ExposureBiasValue: (0, 1),
        },
        "GPS": {},
        "1st": {},
        "Interop": {},
        "thumbnail": None,
    }
    Image.new("RGB", (3024, 4032), (100, 150, 200)).save(
        path, format="HEIF", quality=90, exif=piexif.dump(exif)
    )
    return path


def test_heic_source_preserves_resolution_and_exposure(engine, large_heic, output_dir):
    plan = engine.build_change_plan(
        large_heic, output_dir, preset_id="iphone-13-pro-max", lens_id="main"
    )
    result = engine.apply_metadata(plan)
    assert result.success
    assert result.converted_to_jpeg  # HEIF always converts to JPEG for EXIF visibility

    written = read_summary(result.destination_path)
    assert (written.width, written.height) == (3024, 4032)
    assert written.make == "Apple"
    assert written.model == "iPhone 13 Pro Max"
    assert written.lens_model == "Apple iPhone 13 Pro Max Wide Camera"
    assert written.focal_length_35mm == "26"
    assert written.f_number == "1.5"
    # Shot-specific values from the source HEIC must survive, untouched.
    assert written.iso == 125
    assert written.exposure_time == "1/121"
    assert written.exposure_bias == "0"
    assert result.verification.ok
    assert result.verification.dimensions_ok
