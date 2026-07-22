"""Tests for filename/path safety and output collision handling."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.exceptions import ExportCollisionError
from core.validation import (
    build_output_path,
    ensure_within_directory,
    sanitize_filename,
)


@pytest.mark.parametrize(
    "raw,forbidden",
    [
        ("../../etc/passwd", ".."),
        ("a/b/c.jpg", "/"),
        ("bad\\name.jpg", "\\"),
        ('quote":*.jpg', "*"),
    ],
)
def test_sanitize_strips_dangerous(raw, forbidden):
    safe = sanitize_filename(raw)
    assert forbidden not in safe
    assert "/" not in safe and "\\" not in safe


def test_sanitize_reserved_name():
    assert sanitize_filename("CON.jpg").startswith("_")


def test_sanitize_empty_falls_back():
    assert sanitize_filename("") == "image"
    assert sanitize_filename("   ") == "image"


def test_ensure_within_directory_ok(tmp_path):
    inside = ensure_within_directory(Path("sub/file.jpg"), tmp_path)
    assert str(inside).startswith(str(tmp_path.resolve()))


def test_ensure_within_directory_escape(tmp_path):
    with pytest.raises(ValueError):
        ensure_within_directory(Path("../escape.jpg"), tmp_path)


def test_build_output_path_suffix(tmp_path):
    out = build_output_path(Path("photo.jpg"), tmp_path, suffix="_metadata")
    assert out.name == "photo_metadata.jpg"


def test_build_output_path_increment(tmp_path):
    (tmp_path / "photo_metadata.jpg").write_bytes(b"x")
    out = build_output_path(Path("photo.jpg"), tmp_path, suffix="_metadata")
    assert out.name == "photo_metadata_1.jpg"


def test_build_output_path_error_on_collision(tmp_path):
    (tmp_path / "photo_metadata.jpg").write_bytes(b"x")
    with pytest.raises(ExportCollisionError):
        build_output_path(Path("photo.jpg"), tmp_path, on_collision="error")


def test_build_output_path_preserve_name(tmp_path):
    out = build_output_path(Path("photo.jpg"), tmp_path, preserve_name=True)
    assert out.name == "photo.jpg"
