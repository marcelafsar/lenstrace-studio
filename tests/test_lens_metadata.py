"""Regression tests for the reported bug: device model written but LensModel blank.

Every selected lens must produce a non-empty, correct LensModel in the actual
exported file (read back), across all iPhone presets and the JPEG + PNG paths.
"""

from __future__ import annotations

import pytest

from core.metadata_models import ChangePlan
from core.metadata_reader import read_summary
from core.presets.lens_resolver import resolve_lens_by_id
from core.presets.loader import get_default_loader

# ---- The exact reported scenario ------------------------------------------


@pytest.mark.parametrize(
    "lens_id,expected",
    [
        ("main", "Apple iPhone 13 Pro Max Main Camera"),
        ("ultrawide", "Apple iPhone 13 Pro Max Ultra Wide Camera"),
        ("telephoto", "Apple iPhone 13 Pro Max Telephoto Camera"),
    ],
)
def test_iphone_13_pro_max_lens_written(engine, sample_jpeg, output_dir, lens_id, expected):
    plan = engine.build_change_plan(
        sample_jpeg, output_dir, preset_id="iphone-13-pro-max", lens_id=lens_id
    )
    result = engine.apply_metadata(plan)
    summary = read_summary(result.destination_path)
    assert summary.make == "Apple"
    assert summary.model == "iPhone 13 Pro Max"
    assert summary.lens_model == expected
    assert summary.lens_model  # non-empty
    assert result.verification is not None and result.verification.lens_model_ok


def test_lens_marked_generic(engine, sample_jpeg, output_dir):
    plan = engine.build_change_plan(
        sample_jpeg, output_dir, preset_id="iphone-13-pro-max", lens_id="main"
    )
    assert plan.lens_is_generic is True


# ---- Consistency across every iPhone preset --------------------------------


def test_every_preset_lens_resolves_nonempty():
    loader = get_default_loader()
    for device in loader.list_devices():
        for lens in device.lenses:
            resolved = resolve_lens_by_id(device, lens.id)
            assert resolved is not None
            assert resolved.lens_model.strip(), f"{device.id}/{lens.id} resolved blank"


# ---- keep / remove / switch ------------------------------------------------


def test_keep_original_lens_preserves(engine, tmp_path, output_dir):
    import piexif
    from PIL import Image

    src = tmp_path / "hasLens.jpg"
    exif = {
        "0th": {},
        "Exif": {piexif.ExifIFD.LensModel: b"Original Lens 50mm"},
        "GPS": {},
        "1st": {},
        "Interop": {},
        "thumbnail": None,
    }
    Image.new("RGB", (32, 24), (1, 2, 3)).save(src, format="JPEG", exif=piexif.dump(exif))

    plan = engine.build_change_plan(
        src, output_dir, preset_id="iphone-14-pro", keep_original_lens=True
    )
    result = engine.apply_metadata(plan)
    assert read_summary(result.destination_path).lens_model == "Original Lens 50mm"


def test_remove_lens(engine, tmp_path, output_dir):
    import piexif
    from PIL import Image

    src = tmp_path / "hasLens.jpg"
    exif = {
        "0th": {},
        "Exif": {piexif.ExifIFD.LensModel: b"Original Lens 50mm"},
        "GPS": {},
        "1st": {},
        "Interop": {},
        "thumbnail": None,
    }
    Image.new("RGB", (32, 24), (1, 2, 3)).save(src, format="JPEG", exif=piexif.dump(exif))

    plan = engine.build_change_plan(src, output_dir, remove_lens=True)
    result = engine.apply_metadata(plan)
    assert read_summary(result.destination_path).lens_model is None


def test_switching_lens_clears_stale_optical_fields(engine, tmp_path, output_dir):
    import piexif
    from PIL import Image

    # Source already has a focal length from a different lens.
    src = tmp_path / "stale.jpg"
    exif = {
        "0th": {},
        "Exif": {
            piexif.ExifIFD.LensModel: b"Old Lens",
            piexif.ExifIFD.FocalLength: (7700, 100),  # 77mm
        },
        "GPS": {},
        "1st": {},
        "Interop": {},
        "thumbnail": None,
    }
    Image.new("RGB", (32, 24), (1, 2, 3)).save(src, format="JPEG", exif=piexif.dump(exif))

    # Select a new lens whose preset supplies no focal length.
    plan = engine.build_change_plan(
        src, output_dir, preset_id="iphone-13-pro-max", lens_id="ultrawide"
    )
    result = engine.apply_metadata(plan)
    summary = read_summary(result.destination_path)
    assert summary.lens_model == "Apple iPhone 13 Pro Max Ultra Wide Camera"
    # The unrelated old focal length must not survive.
    assert summary.focal_length is None


# ---- Optical fields are written when supplied ------------------------------


def test_optical_fields_written(engine, sample_jpeg, output_dir):
    # Build a plan that carries optical values directly (as a verified preset would).
    plan = engine.build_change_plan(
        sample_jpeg, output_dir, preset_id="iphone-15-pro", lens_id="main"
    )
    plan = plan.model_copy(
        update={
            "lens_model": "Apple iPhone 15 Pro back triple camera 6.86mm f/1.78",
            "focal_length_mm": 6.86,
            "f_number": 1.78,
            "focal_length_35mm": 24,
            "lens_is_generic": False,
        }
    )
    result = engine.apply_metadata(plan)
    summary = read_summary(result.destination_path)
    assert summary.lens_model.startswith("Apple iPhone 15 Pro")
    assert summary.focal_length == "6.86"
    assert summary.f_number == "1.78"
    assert summary.focal_length_35mm == "24"


# ---- Verification blocks false success -------------------------------------


def test_verification_detects_missing_lens_model(engine, sample_jpeg, output_dir, tmp_path):
    # A plan that requested a lens, but an output file that lacks it.
    plan = ChangePlan(
        source_path=sample_jpeg,
        destination_path=tmp_path / "unused.jpg",
        lens_model="Apple iPhone 13 Pro Max Main Camera",
    )
    # sample_jpeg has no LensModel, so verifying it against the plan must fail.
    verification = engine.verify_exported_metadata(sample_jpeg, plan)
    assert verification.lens_model_ok is False
    assert verification.ok is False


# ---- PNG path ---------------------------------------------------------------


def test_png_export_converts_and_writes_lens(engine, png_image, output_dir):
    plan = engine.build_change_plan(
        png_image, output_dir, preset_id="iphone-16-pro", lens_id="telephoto"
    )
    result = engine.apply_metadata(plan)
    assert result.converted_to_jpeg
    assert result.destination_path.suffix == ".jpg"
    summary = read_summary(result.destination_path)
    assert summary.lens_model == "Apple iPhone 16 Pro Telephoto Camera"
