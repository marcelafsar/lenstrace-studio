"""The one safe, verified file-copy routine used by every provider.

Guarantees:
  * Copies raw bytes with ``shutil.copy2`` — never decodes/re-encodes, never
    uses Pillow, never rewrites metadata.
  * Verifies the destination by size + SHA-256 (unless disabled).
  * Verifies the embedded-metadata summary matches (unless disabled).
  * On any mismatch or error, removes the incomplete destination copy and
    raises :class:`IntegrityVerificationError`.
  * Handles spaces and Unicode filenames (pathlib only, no shell).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from core.delivery.checksums import files_match, sha256_file
from core.delivery.collision import resolve_collision
from core.delivery.exceptions import DestinationInvalidError, IntegrityVerificationError
from core.delivery.metadata_verification import build_export_info, metadata_matches
from core.delivery.models import DeliveryOptions, ExportFileInfo


@dataclass
class TransferOutcome:
    destination_path: Path
    source_info: ExportFileInfo
    destination_info: ExportFileInfo
    checksum_verified: bool
    metadata_verified: bool
    warnings: list[str]


def copy_verified(source: Path, dest_dir: Path, options: DeliveryOptions) -> TransferOutcome:
    """Copy ``source`` into ``dest_dir`` and verify the copy.

    ``dest_dir`` must already exist and be a directory. Returns a
    :class:`TransferOutcome`. Raises :class:`IntegrityVerificationError` if
    verification fails (after cleaning up the partial copy).
    """
    source = Path(source)
    dest_dir = Path(dest_dir)
    if not dest_dir.is_dir():
        raise DestinationInvalidError(
            f"Destination is not a directory: {dest_dir}",
            user_message="The destination folder does not exist.",
        )

    source_info = build_export_info(source)
    dest_path = resolve_collision(dest_dir, source.name, options.collision_strategy)

    warnings: list[str] = []
    try:
        shutil.copy2(source, dest_path)
    except OSError as exc:
        _cleanup(dest_path)
        raise IntegrityVerificationError(
            f"Copy failed: {exc}",
            user_message="The file could not be copied to the destination.",
        ) from exc

    checksum_verified = False
    metadata_verified = False
    try:
        if options.verify_checksum:
            if not files_match(source, dest_path):
                raise IntegrityVerificationError(
                    "SHA-256/size mismatch after copy",
                    user_message="The copied file did not match the original and was removed.",
                )
            checksum_verified = True

        dest_info = build_export_info(dest_path)

        if options.verify_metadata:
            if not metadata_matches(source_info, dest_info):
                raise IntegrityVerificationError(
                    "Embedded metadata mismatch after copy",
                    user_message="The copied file's metadata did not match and was removed.",
                )
            metadata_verified = True
    except IntegrityVerificationError:
        _cleanup(dest_path)
        raise

    if not options.verify_checksum:
        warnings.append("Checksum verification was disabled for this copy.")

    return TransferOutcome(
        destination_path=dest_path,
        source_info=source_info,
        destination_info=dest_info,
        checksum_verified=checksum_verified,
        metadata_verified=metadata_verified,
        warnings=warnings,
    )


def _cleanup(path: Path) -> None:
    """Remove an incomplete destination copy, ignoring further errors."""
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def quick_sha256(path: Path) -> str:
    """Convenience re-export used by providers that only need the hash."""
    return sha256_file(path)
