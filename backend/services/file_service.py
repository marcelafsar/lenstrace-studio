"""File-handling service: secure upload storage and thumbnails.

All uploaded bytes are written inside the backend's per-run working directory
with sanitised names. Nothing is uploaded to any external server; processing is
entirely local.
"""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

from backend.config import get_settings
from backend.logging_config import get_logger, safe_path
from backend.services.session_service import FileEntry, get_session_store
from core.exceptions import CorruptImageError, UnsupportedImageFormatError
from core.metadata_models import ImageFormat
from core.metadata_reader import detect_format, is_supported
from core.validation import sanitize_filename

logger = get_logger(__name__)


def save_upload(data: bytes, original_name: str) -> FileEntry:
    """Persist uploaded bytes to the working dir and register a session entry."""
    settings = get_settings()
    if len(data) > settings.max_upload_bytes:
        raise UnsupportedImageFormatError(
            "Upload exceeds size limit",
            user_message=f"File is larger than the {settings.max_upload_mb} MB limit.",
        )

    uploads = settings.work_dir / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(original_name)
    dest = _unique_path(uploads / safe_name)
    dest.write_bytes(data)

    # Reject anything that is not a real, supported image.
    try:
        supported = is_supported(dest)
    except UnsupportedImageFormatError:
        # HEIF without the optional dep, etc. — keep the file but surface it.
        raise
    if not supported:
        dest.unlink(missing_ok=True)
        raise CorruptImageError(
            "Uploaded file is not a recognised image",
            user_message="This file is not a supported image format.",
        )

    logger.info("Stored upload %s (%d bytes)", safe_path(dest), len(data))
    return get_session_store().register(dest, original_name)


def make_thumbnail_data_uri(path: Path, max_side: int = 320) -> str:
    """Return a small base64 PNG data URI for previewing in the UI."""
    from PIL import Image

    try:
        with Image.open(path) as opened:
            rgb = opened.convert("RGB")
            rgb.thumbnail((max_side, max_side))
            buf = BytesIO()
            rgb.save(buf, format="PNG")
    except Exception as exc:  # noqa: BLE001
        raise CorruptImageError(
            f"Cannot render thumbnail for {safe_path(path)}: {exc}",
            user_message="A preview could not be generated for this image.",
        ) from exc
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def format_label(fmt: ImageFormat) -> str:
    return fmt.value


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    counter = 1
    while True:
        candidate = path.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def resolve_format(path: Path) -> ImageFormat:
    return detect_format(path)
