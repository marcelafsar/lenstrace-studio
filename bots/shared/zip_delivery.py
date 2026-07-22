"""Metadata-safe ZIP delivery for platforms (Discord) that may strip EXIF from
saved image previews.

Saving a rendered chat preview can silently re-encode an image, dropping the
metadata LensTrace just wrote. Wrapping the verified export in a ZIP forces a
real file download instead, so the bytes a user imports into Photos are
byte-for-byte identical to the verified export. The archive also carries a
checksum manifest and a short human-readable report so the result is auditable
without re-opening the image.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from core.audit import AUDIT_DISCLAIMER
from core.delivery.checksums import sha256_file
from core.metadata_models import ChangeDiff, ExportResult
from core.validation import sanitize_filename

README_TEXT = (
    "LensTrace Studio — metadata-safe export\n"
    "========================================\n\n"
    "This ZIP preserves the exact metadata LensTrace wrote. Discord's image\n"
    "preview may strip metadata if you save it directly, so:\n\n"
    "1. Download this ZIP as a file (do not long-press/save the chat preview).\n"
    "2. Open it in Files.\n"
    "3. Extract it.\n"
    "4. Import the extracted image into Photos.\n\n"
    "metadata-report.json lists what was preserved, changed, and removed.\n"
    "SHA256SUMS.txt lets you independently verify the image was not altered.\n"
)

DIRECT_ATTACHMENT_WARNING = (
    "⚠️ Saving the rendered Discord preview may remove metadata. "
    "Download the original attachment file, or use Metadata-safe ZIP instead."
)


def build_metadata_report(
    result: ExportResult, diff: ChangeDiff, image_name: str, checksum: str
) -> dict:
    """Assemble the JSON-serialisable preservation report bundled in the ZIP."""
    verification = result.verification.model_dump() if result.verification else None
    return {
        "tool": "LensTrace Studio",
        "disclaimer": AUDIT_DISCLAIMER,
        "image_filename": image_name,
        "sha256": checksum,
        "converted_to_jpeg": result.converted_to_jpeg,
        "preserved_fields": [row.field for row in diff.rows if row.status == "preserved"],
        "changed_fields": [row.field for row in diff.rows if row.status in ("changed", "added")],
        "removed_fields": [row.field for row in diff.rows if row.status == "removed"],
        "warnings": list(result.warnings),
        "verification": verification,
    }


def build_metadata_safe_zip(result: ExportResult, diff: ChangeDiff, zip_path: Path) -> Path:
    """Build the metadata-safe ZIP at ``zip_path`` and return it.

    The ZIP contains the exact exported image bytes, a metadata-report.json,
    a SHA256SUMS.txt, and a README.txt. All archive member names are fixed or
    derived via :func:`sanitize_filename` (a single safe basename, never a
    caller-controlled path), so path traversal is not possible. The archive is
    read back and independently re-verified before being handed to the caller.
    """
    image_path = Path(result.destination_path)
    image_name = sanitize_filename(image_path.name)
    checksum = result.sha256 or sha256_file(image_path)

    report = build_metadata_report(result, diff, image_name, checksum)
    checksums_txt = f"{checksum}  {image_name}\n"

    zip_path = Path(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(image_path, arcname=image_name)
        zf.writestr("metadata-report.json", json.dumps(report, indent=2, ensure_ascii=False))
        zf.writestr("SHA256SUMS.txt", checksums_txt)
        zf.writestr("README.txt", README_TEXT)

    _verify_zip(zip_path, image_name, checksum)
    return zip_path


def _verify_zip(zip_path: Path, image_name: str, expected_sha256: str) -> None:
    """Re-open the just-built ZIP and confirm its contents are safe and correct."""
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        for name in names:
            if name.startswith("/") or Path(name).is_absolute() or ".." in Path(name).parts:
                raise ValueError(f"Unsafe member path in generated ZIP: {name!r}")
        if image_name not in names:
            raise ValueError("Exported image is missing from the generated ZIP")
        data = zf.read(image_name)
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("ZIP image checksum does not match the verified export")
