"""Shared image acceptance + content validation for both bots.

Two-stage check:
  1. ``accept_document`` — cheap gate on the *declared* type: an image MIME, or a
     supported filename extension when the MIME is missing/octet-stream. This is
     what lets iOS/desktop image documents (often ``application/octet-stream``)
     through the handler.
  2. ``validate_image_content`` — authoritative check that the downloaded bytes
     are actually a supported image, via the shared metadata engine (Pillow).

Only formats the LensTrace engine can actually read are accepted. HEIC/HEIF is
accepted only when the optional ``pillow-heif`` dependency is installed.
"""

from __future__ import annotations

from pathlib import Path

from core.exceptions import CorruptImageError, UnsupportedImageFormatError
from core.metadata_models import ImageFormat, MetadataSummary
from core.metadata_reader import _HEIF_AVAILABLE, detect_format, read_summary

# Extensions whose content the engine can read. HEIC/HEIF only if supported.
_BASE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
_HEIF_EXTENSIONS = {".heic", ".heif"}


def supported_extensions() -> set[str]:
    exts = set(_BASE_EXTENSIONS)
    if _HEIF_AVAILABLE:
        exts |= _HEIF_EXTENSIONS
    return exts


def is_supported_extension(filename: str | None) -> bool:
    if not filename:
        return False
    return Path(filename).suffix.lower() in supported_extensions()


def is_image_mime(mime: str | None) -> bool:
    return mime is not None and mime.lower().startswith("image/")


def accept_document(filename: str | None, mime: str | None) -> bool:
    """Cheap gate: accept if the MIME is an image, or (MIME absent/generic) the
    filename has a supported extension. Never accepts on extension alone when the
    MIME clearly says it is a non-image type.
    """
    if is_image_mime(mime):
        return True
    # Missing or generic binary MIME → fall back to a supported extension.
    generic = mime is None or mime.lower() in {
        "application/octet-stream",
        "application/binary",
        "binary/octet-stream",
        "",
    }
    return bool(generic and is_supported_extension(filename))


def validate_image_content(path: Path) -> MetadataSummary:
    """Confirm the file is really a supported image; return its summary.

    Raises :class:`UnsupportedImageFormatError` for a recognised-but-unsupported
    format (e.g. HEIC without pillow-heif) and :class:`CorruptImageError` for
    anything that is not a decodable image.
    """
    path = Path(path)
    fmt = detect_format(path)
    if fmt == ImageFormat.UNKNOWN:
        raise CorruptImageError(
            f"Unrecognised image content: {path.name}",
            user_message="That file is not a supported image, or it is damaged.",
        )
    if fmt == ImageFormat.HEIF and not _HEIF_AVAILABLE:
        raise UnsupportedImageFormatError(
            "HEIF without pillow-heif",
            user_message="HEIC/HEIF images need the optional 'pillow-heif' package on the server.",
        )
    # read_summary decodes enough to confirm the image is valid.
    return read_summary(path)
