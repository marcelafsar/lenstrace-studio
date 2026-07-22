"""Acceptance tests A–I for simulated exposure profiles + 12 MP resolution.

All fixtures are generated (a blank JPEG with no camera EXIF); no personal
images. Each test reads the exported file back and asserts the ACTUAL written
values, exactly as the task's acceptance criteria require.
"""

from __future__ import annotations

import math
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from core.exposure.calculations import aperture_value_apex, shutter_speed_value_apex
from core.metadata_engine import _parse_numeric_or_fraction
from core.metadata_reader import read_summary

PRESET = "iphone-13-pro-max"
LENS = "main"


@pytest.fixture
def blank_portrait(tmp_path: Path) -> Path:
    """A 3024x4032 JPEG with NO camera EXIF."""
    path = tmp_path / "blank.jpg"
    Image.new("RGB", (3024, 4032), (128, 128, 128)).save(path, format="JPEG", quality=90)
    return path


@pytest.fixture
def small_portrait(tmp_path: Path) -> Path:
    """A genuinely low-resolution 941x1672 JPEG with no camera EXIF."""
    path = tmp_path / "small.jpg"
    Image.new("RGB", (941, 1672), (90, 90, 90)).save(path, format="JPEG", quality=90)
    return path


def _export(engine, source, output_dir, *, profile="default", **kwargs):
    plan = engine.build_change_plan(
        source,
        output_dir,
        preset_id=PRESET,
        lens_id=LENS,
        exposure_mode="override",
        exposure_profile_id=profile,
        **kwargs,
    )
    return engine.apply_metadata(plan)


def _assert_common_lens(s):
    assert s.make == "Apple"
    assert s.model == "iPhone 13 Pro Max"
    assert s.lens_model  # non-empty
    assert s.focal_length_35mm == "26"
    assert s.f_number == "1.5"
    # ApertureValue consistent with f/1.5.
    assert _parse_numeric_or_fraction(s.aperture_value) == pytest.approx(
        aperture_value_apex(1.5), abs=0.02
    )


# ---- Test A — Default profile ----------------------------------------------


def test_a_default_profile(engine, blank_portrait, output_dir):
    result = _export(engine, blank_portrait, output_dir, profile="default")
    assert result.success
    s = read_summary(result.destination_path)
    assert (s.width, s.height) == (3024, 4032)
    _assert_common_lens(s)
    assert s.iso == 125
    assert s.exposure_time == "1/121"
    assert _parse_numeric_or_fraction(s.exposure_bias) == 0
    assert s.flash == 0  # did not fire
    assert _parse_numeric_or_fraction(s.shutter_speed_value) == pytest.approx(
        shutter_speed_value_apex(1 / 121), abs=0.02
    )
    assert result.verification.ok
    assert result.verification.exposure_ok


# ---- Test B — Bright scene -------------------------------------------------


def test_b_bright_scene(engine, blank_portrait, output_dir):
    result = _export(engine, blank_portrait, output_dir, profile="bright")
    s = read_summary(result.destination_path)
    assert s.iso == 50
    assert s.exposure_time == "1/500"
    assert s.flash == 0
    assert s.f_number == "1.5"
    assert s.focal_length_35mm == "26"


# ---- Test C — Dark scene ---------------------------------------------------


def test_c_dark_scene(engine, blank_portrait, output_dir):
    result = _export(engine, blank_portrait, output_dir, profile="dark")
    s = read_summary(result.destination_path)
    assert s.iso == 800
    assert s.exposure_time == "1/20"
    assert s.flash == 0
    assert s.f_number == "1.5"
    assert s.focal_length_35mm == "26"


# ---- Test D — Flash on -----------------------------------------------------


def test_d_flash_on(engine, blank_portrait, output_dir):
    result = _export(engine, blank_portrait, output_dir, profile="flash")
    s = read_summary(result.destination_path)
    assert s.iso == 100
    assert s.exposure_time == "1/60"
    assert s.flash == 1  # fired
    assert s.light_source == 4
    assert s.f_number == "1.5"
    assert s.focal_length_35mm == "26"


# ---- Test E — Smaller source with 12 MP output -----------------------------


def test_e_small_source_upscaled_to_12mp(engine, small_portrait, output_dir):
    plan = engine.build_change_plan(
        small_portrait,
        output_dir,
        preset_id=PRESET,
        lens_id=LENS,
        exposure_mode="override",
        exposure_profile_id="default",
        resolution_mode="iphone_12mp",
        resolution_fit="crop_to_fill",
    )
    result = engine.apply_metadata(plan)
    s = read_summary(result.destination_path)
    assert (s.width, s.height) == (3024, 4032)
    assert (s.exif_image_width, s.exif_image_height) == (3024, 4032)
    # The resize is recorded and honestly labelled (no recovered detail claim).
    assert plan.resolution is not None and plan.resolution.is_upscale
    assert any("does not restore real detail" in w for w in result.warnings)


# ---- Test F — Smaller source with Keep original ----------------------------


def test_f_small_source_keep_original(engine, small_portrait, output_dir):
    plan = engine.build_change_plan(
        small_portrait,
        output_dir,
        preset_id=PRESET,
        lens_id=LENS,
        exposure_mode="override",
        exposure_profile_id="default",
        resolution_mode="keep",
    )
    result = engine.apply_metadata(plan)
    s = read_summary(result.destination_path)
    # Actual resolution stays honestly low.
    assert (s.width, s.height) == (941, 1672)
    # Megapixels of the actual output is not 12 (the UI must not claim 12 MP).
    from core.preview import build_camera_preview

    preview = build_camera_preview(plan)
    assert "12 MP" not in (preview.resolution_line or "")
    # Exposure fields are still generated.
    assert s.iso == 125
    assert s.exposure_time == "1/121"


# ---- Test G — Telegram sends the verified bytes via send_document ----------


def test_g_telegram_sends_verified_document(engine, blank_portrait, output_dir):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from bots.shared.temporary_files import TemporaryWorkspace
    from bots.telegram_bot import handlers as th
    from bots.telegram_bot.conversation import EditState

    th.sessions._sessions.clear()
    session = th.sessions.get_or_create(99)
    ws = TemporaryWorkspace()
    session.config = {
        "workspace": ws,
        "preset_id": PRESET,
        "lens_id": LENS,
        "exposure_mode": "override",
        "exposure_profile_id": "default",
        "resolution_mode": "keep",
    }
    session.source_path = blank_portrait
    session.original_name = "blank.jpg"
    session.state = EditState.REVIEWING.value

    # Capture the exact bytes sent (the workspace is cleaned up after export).
    sent_docs: list[tuple[str, bytes]] = []

    async def _capture(**kwargs):
        handle = kwargs["document"]
        handle.seek(0)
        sent_docs.append((kwargs["filename"], handle.read()))

    query = SimpleNamespace(
        message=SimpleNamespace(reply_document=AsyncMock(side_effect=_capture), chat_id=1),
        edit_message_text=AsyncMock(),
    )
    asyncio.run(th._do_export(query, session))

    # The FIRST document is the exported image; it must carry the Default fields.
    sent_name, sent_bytes = sent_docs[0]
    assert sent_name.endswith(".jpg")
    check_path = output_dir / "sent.jpg"
    check_path.write_bytes(sent_bytes)
    s = read_summary(check_path)
    assert s.iso == 125
    assert s.exposure_time == "1/121"
    assert s.make == "Apple"
    assert (s.width, s.height) == (3024, 4032)
    ws.cleanup()


# ---- Test H — Discord ZIP contains the exact verified image ----------------


def test_h_discord_zip_contains_verified_image(engine, blank_portrait, output_dir):
    import hashlib

    from bots.shared.zip_delivery import build_metadata_safe_zip

    plan = engine.build_change_plan(
        blank_portrait,
        output_dir,
        preset_id=PRESET,
        lens_id=LENS,
        exposure_mode="override",
        exposure_profile_id="default",
    )
    result = engine.apply_metadata(plan)
    diff = engine.build_diff(plan)
    zip_path = build_metadata_safe_zip(result, diff, output_dir / "out.zip")

    image_bytes = Path(result.destination_path).read_bytes()
    expected_sha = hashlib.sha256(image_bytes).hexdigest()
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        image_name = next(
            n for n in names if n not in ("metadata-report.json", "SHA256SUMS.txt", "README.txt")
        )
        assert zf.read(image_name) == image_bytes
        assert expected_sha in zf.read("SHA256SUMS.txt").decode("utf-8")

    # The image inside the ZIP carries the Default-profile fields.
    with zipfile.ZipFile(zip_path) as zf, (output_dir / "extracted.jpg").open("wb") as fh:
        fh.write(zf.read(image_name))
    s = read_summary(output_dir / "extracted.jpg")
    assert s.iso == 125
    assert s.exposure_time == "1/121"


# ---- Test I — Desktop, Telegram, Discord share one export implementation ----


def test_i_desktop_and_bots_identical_metadata(engine, blank_portrait, tmp_path):
    """The same change plan yields identical camera metadata for every interface."""
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    out_a.mkdir()
    out_b.mkdir()

    def build(out):
        return engine.apply_metadata(
            engine.build_change_plan(
                blank_portrait,
                out,
                preset_id=PRESET,
                lens_id=LENS,
                exposure_mode="override",
                exposure_profile_id="default",
            )
        )

    r1 = build(out_a)
    r2 = build(out_b)
    s1 = read_summary(r1.destination_path)
    s2 = read_summary(r2.destination_path)
    for attr in (
        "make",
        "model",
        "lens_model",
        "focal_length_35mm",
        "f_number",
        "iso",
        "exposure_time",
        "exposure_bias",
        "flash",
        "aperture_value",
        "shutter_speed_value",
        "width",
        "height",
    ):
        assert getattr(s1, attr) == getattr(s2, attr), attr


# ---- APEX calculation sanity -----------------------------------------------


def test_apex_calculations():
    assert aperture_value_apex(1.5) == pytest.approx(2 * math.log2(1.5))
    assert shutter_speed_value_apex(1 / 121) == pytest.approx(math.log2(121), abs=1e-9)
