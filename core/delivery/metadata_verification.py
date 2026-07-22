"""Capture and compare the integrity record of an exported file.

Uses the existing :mod:`core.metadata_reader` so the same EXIF interpretation
is applied everywhere. Never modifies the file.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from core.delivery.checksums import sha256_file
from core.delivery.models import ExportFileInfo
from core.metadata_models import MetadataSummary
from core.metadata_reader import read_summary

_MIME_BY_FORMAT = {
    "JPEG": "image/jpeg",
    "TIFF": "image/tiff",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "HEIF": "image/heif",
}


def _gps_summary(summary: MetadataSummary) -> str:
    if summary.has_gps and summary.gps_latitude is not None and summary.gps_longitude is not None:
        # Coarse label only; never log/return precise coordinates from here.
        return "present"
    return "none"


def build_export_info(path: Path) -> ExportFileInfo:
    """Read a file's integrity record (checksum + key metadata)."""
    path = Path(path)
    summary = read_summary(path)
    mime = _MIME_BY_FORMAT.get(summary.image_format.value) or (mimetypes.guess_type(path.name)[0])
    return ExportFileInfo(
        filename=path.name,
        image_format=summary.image_format.value,
        mime_type=mime,
        width=summary.width,
        height=summary.height,
        size_bytes=path.stat().st_size,
        sha256=sha256_file(path),
        exif_make=summary.make,
        exif_model=summary.model,
        lens_model=summary.lens_model,
        datetime_original=summary.datetime_original,
        offset_time_original=summary.offset_time_original,
        gps_summary=_gps_summary(summary),
    )


def metadata_matches(a: ExportFileInfo, b: ExportFileInfo) -> bool:
    """Return True if the key embedded-metadata fields are identical.

    Compares the fields a user cares about after a byte-for-byte copy. The
    filenames may legitimately differ (collision suffix), so filename is
    excluded; the checksum comparison already proves the bytes are identical.
    """
    fields = (
        "image_format",
        "width",
        "height",
        "exif_make",
        "exif_model",
        "lens_model",
        "datetime_original",
        "offset_time_original",
        "gps_summary",
    )
    return all(getattr(a, f) == getattr(b, f) for f in fields)
