"""Tests for the Discord metadata-safe ZIP builder."""

from __future__ import annotations

import zipfile
from pathlib import Path

from bots.shared.zip_delivery import build_metadata_safe_zip
from core.metadata_models import ChangeDiff, FieldChange


def _fake_result(destination_path: Path, tmp_path: Path):
    from core.metadata_models import ExportResult

    return ExportResult(
        source_path=tmp_path / "src.jpg",
        destination_path=destination_path,
        bytes_written=destination_path.stat().st_size,
        sha256=None,
        success=True,
    )


def test_zip_contains_exact_image_bytes_and_manifest(tmp_path):
    image = tmp_path / "export.jpg"
    image.write_bytes(b"fake-jpeg-bytes")
    result = _fake_result(image, tmp_path)
    diff = ChangeDiff(
        rows=[
            FieldChange(
                field="Model", original="OldModel", new="iPhone 13 Pro Max", status="changed"
            ),
            FieldChange(field="Software", original="1.0", new="1.0", status="preserved"),
        ]
    )

    zip_path = build_metadata_safe_zip(result, diff, tmp_path / "out.zip")

    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        assert names == {"export.jpg", "metadata-report.json", "SHA256SUMS.txt", "README.txt"}
        assert zf.read("export.jpg") == b"fake-jpeg-bytes"
        report = zf.read("metadata-report.json").decode("utf-8")
        assert '"Model"' in report
        assert "changed_fields" in report
        checksums = zf.read("SHA256SUMS.txt").decode("utf-8")
        assert "export.jpg" in checksums


def test_zip_checksum_matches_sha256sums(tmp_path):
    import hashlib

    image = tmp_path / "export.jpg"
    image.write_bytes(b"some bytes to hash")
    expected = hashlib.sha256(image.read_bytes()).hexdigest()
    result = _fake_result(image, tmp_path)

    zip_path = build_metadata_safe_zip(result, ChangeDiff(), tmp_path / "out.zip")

    with zipfile.ZipFile(zip_path) as zf:
        checksums = zf.read("SHA256SUMS.txt").decode("utf-8")
        assert expected in checksums
        report = zf.read("metadata-report.json").decode("utf-8")
        assert expected in report


def test_zip_arcname_is_sanitized_never_a_path(tmp_path):
    # A destination filename can only ever be what build_output_path produced
    # (already sanitized), but confirm the archive member is a bare filename
    # even if the path on disk has directory components.
    nested = tmp_path / "nested" / "dir"
    nested.mkdir(parents=True)
    image = nested / "export.jpg"
    image.write_bytes(b"data")
    result = _fake_result(image, tmp_path)

    zip_path = build_metadata_safe_zip(result, ChangeDiff(), tmp_path / "out.zip")

    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            assert not name.startswith("/")
            assert ".." not in Path(name).parts
            assert Path(name).name == name  # single path component only
