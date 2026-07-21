"""Tests for the core delivery primitives: checksums, collision, transfer, URLs."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.delivery.checksums import files_match, sha256_file
from core.delivery.collision import resolve_collision
from core.delivery.exceptions import (
    DeliveryError,
    IntegrityVerificationError,
    UnsafeUrlError,
)
from core.delivery.metadata_verification import build_export_info, metadata_matches
from core.delivery.models import DeliveryOptions
from core.delivery.transfer import copy_verified
from core.delivery.validation import validate_destination_dir, validate_external_url

# ---- Checksums -----------------------------------------------------------


def test_sha256_matches_hashlib(sample_jpeg):
    import hashlib

    expected = hashlib.sha256(sample_jpeg.read_bytes()).hexdigest()
    assert sha256_file(sample_jpeg) == expected


def test_files_match(sample_jpeg, tmp_path):
    copy = tmp_path / "copy.jpg"
    copy.write_bytes(sample_jpeg.read_bytes())
    assert files_match(sample_jpeg, copy)
    copy.write_bytes(b"different")
    assert not files_match(sample_jpeg, copy)


# ---- Collision -----------------------------------------------------------


def test_collision_increment_windows_style(tmp_path):
    (tmp_path / "photo.jpg").write_bytes(b"x")
    (tmp_path / "photo (1).jpg").write_bytes(b"x")
    result = resolve_collision(tmp_path, "photo.jpg")
    assert result.name == "photo (2).jpg"


def test_collision_no_conflict(tmp_path):
    assert resolve_collision(tmp_path, "fresh.jpg").name == "fresh.jpg"


def test_collision_error_strategy(tmp_path):
    (tmp_path / "photo.jpg").write_bytes(b"x")
    with pytest.raises(DeliveryError):
        resolve_collision(tmp_path, "photo.jpg", strategy="error")


# ---- Verified transfer ---------------------------------------------------


def test_copy_verified_success(sample_jpeg, tmp_path):
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    outcome = copy_verified(sample_jpeg, dest_dir, DeliveryOptions())
    assert outcome.checksum_verified and outcome.metadata_verified
    assert files_match(sample_jpeg, outcome.destination_path)
    # Original is untouched.
    assert sample_jpeg.exists()


def test_copy_verified_source_unchanged(sample_jpeg, tmp_path):
    before = sample_jpeg.read_bytes()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    copy_verified(sample_jpeg, dest_dir, DeliveryOptions())
    assert sample_jpeg.read_bytes() == before


def test_copy_verified_collision(sample_jpeg, tmp_path):
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    first = copy_verified(sample_jpeg, dest_dir, DeliveryOptions())
    second = copy_verified(sample_jpeg, dest_dir, DeliveryOptions())
    assert first.destination_path.name == sample_jpeg.name
    assert second.destination_path.name == f"{sample_jpeg.stem} (1){sample_jpeg.suffix}"


def test_copy_verified_unicode_and_spaces(tmp_path):
    from PIL import Image

    src = tmp_path / "phóto with spaces café.jpg"
    Image.new("RGB", (10, 10), (1, 2, 3)).save(src, format="JPEG")
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    outcome = copy_verified(src, dest_dir, DeliveryOptions())
    assert outcome.destination_path.name == "phóto with spaces café.jpg"
    assert files_match(src, outcome.destination_path)


def test_copy_verified_missing_dest_dir(sample_jpeg, tmp_path):
    from core.delivery.exceptions import DestinationInvalidError

    with pytest.raises(DestinationInvalidError):
        copy_verified(sample_jpeg, tmp_path / "does-not-exist", DeliveryOptions())


def test_copy_verified_cleanup_on_checksum_failure(sample_jpeg, tmp_path, monkeypatch):
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    # Force a checksum mismatch so the incomplete copy must be removed.
    import core.delivery.transfer as transfer

    monkeypatch.setattr(transfer, "files_match", lambda a, b: False)
    with pytest.raises(IntegrityVerificationError):
        copy_verified(sample_jpeg, dest_dir, DeliveryOptions())
    # No leftover file in the destination.
    assert list(dest_dir.iterdir()) == []


# ---- Metadata verification ----------------------------------------------


def test_build_export_info(sample_jpeg):
    info = build_export_info(sample_jpeg)
    assert info.filename == "sample.jpg"
    assert info.image_format == "JPEG"
    assert info.mime_type == "image/jpeg"
    assert len(info.sha256) == 64
    assert info.size_bytes > 0


def test_metadata_matches_identical_copy(sample_jpeg, tmp_path):
    copy = tmp_path / "copy.jpg"
    copy.write_bytes(sample_jpeg.read_bytes())
    assert metadata_matches(build_export_info(sample_jpeg), build_export_info(copy))


# ---- URL validation ------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    ["https://pairdrop.net/", "http://localhost:8080/", "http://127.0.0.1:5000/x"],
)
def test_valid_urls(url):
    assert validate_external_url(url).startswith(("http://", "https://"))


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,x",
        "file:///etc/passwd",
        "http://example.com",  # non-local http
        "https://user:pass@example.com/",
        "ftp://host/f",
        "",
    ],
)
def test_invalid_urls(url):
    with pytest.raises(UnsafeUrlError):
        validate_external_url(url)


def test_validate_destination_dir_ok(tmp_path):
    assert validate_destination_dir(tmp_path) == tmp_path.resolve()


def test_validate_destination_dir_rejects_unc():
    from core.delivery.exceptions import DestinationInvalidError

    with pytest.raises(DestinationInvalidError):
        validate_destination_dir(Path(r"\\server\share\folder"))


def test_validate_destination_dir_rejects_missing(tmp_path):
    from core.delivery.exceptions import DestinationInvalidError

    with pytest.raises(DestinationInvalidError):
        validate_destination_dir(tmp_path / "nope")
