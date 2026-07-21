"""Write a validated :class:`ChangePlan` into a NEW image copy.

Design rules enforced here:
  * The source file is never modified. We copy pixels first, then edit EXIF on
    the copy.
  * For JPEG/TIFF we edit only the EXIF segment, so pixels are not recompressed.
  * PNG/WEBP/HEIF cannot reliably store the full EXIF set; the engine may
    convert to JPEG (which recompresses) and records a warning.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from core.datetime_utils import format_exif_datetime
from core.exceptions import MetadataWriteError, UnsupportedImageFormatError
from core.gps import build_gps_ifd
from core.metadata_models import ChangePlan, DateStrategy, ExportResult, ImageFormat
from core.metadata_reader import detect_format

# Formats whose EXIF we can edit in place without touching pixels.
_EXIF_NATIVE = {ImageFormat.JPEG, ImageFormat.TIFF}
# Formats we can convert to JPEG on request.
_CONVERTIBLE = {ImageFormat.PNG, ImageFormat.WEBP, ImageFormat.HEIF}


def _empty_exif() -> dict:
    return {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "Interop": {}, "thumbnail": None}


def _rational(value: float, denom: int = 100) -> tuple[int, int]:
    """Convert a positive float to an EXIF unsigned rational (num, denom)."""
    return (int(round(value * denom)), denom)


def _apply_lens_fields(exif_ifd: dict, plan: ChangePlan) -> None:
    """Write/keep/remove lens EXIF fields on the Exif IFD.

    Rules:
      * keep_original_lens  -> leave every existing lens field untouched.
      * remove_lens         -> delete all lens fields.
      * a selected lens     -> set LensModel (never blank) and any optical values
        the preset provided, and clear stale optical fields the new lens does not
        define (so an unrelated old focal length is never left behind).
    """
    import piexif

    lens_tags = (
        piexif.ExifIFD.LensModel,
        piexif.ExifIFD.FocalLength,
        piexif.ExifIFD.FNumber,
        piexif.ExifIFD.FocalLengthIn35mmFilm,
        piexif.ExifIFD.LensSpecification,
    )

    if plan.keep_original_lens:
        return
    if plan.remove_lens:
        for tag in lens_tags:
            exif_ifd.pop(tag, None)
        return
    if not plan.lens_model:
        return  # no lens selected; leave existing lens fields as-is

    # A new lens is being applied: clear all lens tags first, then set ours.
    for tag in lens_tags:
        exif_ifd.pop(tag, None)
    exif_ifd[piexif.ExifIFD.LensModel] = plan.lens_model.encode("utf-8")
    if plan.focal_length_mm is not None:
        exif_ifd[piexif.ExifIFD.FocalLength] = _rational(plan.focal_length_mm)
    if plan.f_number is not None:
        exif_ifd[piexif.ExifIFD.FNumber] = _rational(plan.f_number)
    if plan.focal_length_35mm is not None:
        exif_ifd[piexif.ExifIFD.FocalLengthIn35mmFilm] = int(round(plan.focal_length_35mm))
    if plan.lens_specification is not None and len(plan.lens_specification) == 4:
        exif_ifd[piexif.ExifIFD.LensSpecification] = [_rational(v) for v in plan.lens_specification]


def _build_exif_dict(base: dict, plan: ChangePlan) -> dict:
    """Apply the change plan onto a piexif-style dict and return it."""
    import piexif

    exif = {k: dict(v) if isinstance(v, dict) else v for k, v in base.items()}
    for key in ("0th", "Exif", "GPS", "1st", "Interop"):
        exif.setdefault(key, {})

    zeroth = exif["0th"]
    exif_ifd = exif["Exif"]

    def set_str(ifd: dict, tag: int, value: str | None) -> None:
        if value is not None:
            ifd[tag] = value.encode("utf-8")

    # Device identity
    set_str(zeroth, piexif.ImageIFD.Make, plan.make)
    set_str(zeroth, piexif.ImageIFD.Model, plan.model)
    set_str(zeroth, piexif.ImageIFD.Software, plan.software)

    # Lens fields (LensModel plus any optical values the preset supplied).
    _apply_lens_fields(exif_ifd, plan)

    # Date / time
    if plan.date_strategy == DateStrategy.SET_EXPLICIT:
        if plan.datetime_original is not None:
            stamp = format_exif_datetime(plan.datetime_original)
            set_str(exif_ifd, piexif.ExifIFD.DateTimeOriginal, stamp)
        if plan.create_date is not None:
            set_str(
                exif_ifd,
                piexif.ExifIFD.DateTimeDigitized,
                format_exif_datetime(plan.create_date),
            )
        if plan.modify_date is not None:
            set_str(zeroth, piexif.ImageIFD.DateTime, format_exif_datetime(plan.modify_date))
        if plan.utc_offset is not None:
            set_str(exif_ifd, piexif.ExifIFD.OffsetTime, plan.utc_offset)
            set_str(exif_ifd, piexif.ExifIFD.OffsetTimeOriginal, plan.utc_offset)
            set_str(exif_ifd, piexif.ExifIFD.OffsetTimeDigitized, plan.utc_offset)

    # GPS
    if plan.remove_gps:
        exif["GPS"] = {}
    elif plan.gps is not None:
        exif["GPS"] = build_gps_ifd(plan.gps.latitude, plan.gps.longitude, plan.gps.altitude_m)

    # Explicit tag removal ("0th:271" style keys or piexif ints are not accepted;
    # tags_to_remove holds field names handled by the engine before this point).
    return exif


def write_metadata(base_exif: dict, plan: ChangePlan) -> ExportResult:
    """Produce the exported copy described by ``plan``.

    ``base_exif`` is the source image's current EXIF (piexif-style dict), or an
    empty dict. Returns an :class:`ExportResult`.
    """
    import piexif

    source = Path(plan.source_path)
    dest = Path(plan.destination_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    src_format = detect_format(source)
    warnings: list[str] = []
    converted = False

    if plan.strip_all_metadata:
        return _write_stripped(source, dest, src_format)

    # Convertible if the format can't hold EXIF, OR the user asked for JPEG
    # output from a non-JPEG source (broad Apple Photos visibility).
    force_jpeg = plan.convert_to_jpeg and src_format != ImageFormat.JPEG
    if src_format in _EXIF_NATIVE and not force_jpeg:
        working_dest = dest
    elif src_format in _CONVERTIBLE or force_jpeg:
        working_dest, converted, warn = _convert_to_jpeg(source, dest)
        if warn:
            warnings.append(warn)
        base_exif = _empty_exif()  # converted image starts without prior EXIF
    else:
        raise UnsupportedImageFormatError(
            f"Cannot write metadata for format {src_format}",
            user_message="This image format is not supported for metadata writing.",
        )

    if not converted:
        shutil.copy2(source, working_dest)

    exif_dict = _build_exif_dict(base_exif, plan)
    try:
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, str(working_dest))
    except Exception as exc:  # noqa: BLE001 - piexif raises broad errors
        raise MetadataWriteError(
            f"Failed to write EXIF to {working_dest}: {exc}",
            user_message="The new metadata could not be written to the exported copy.",
        ) from exc

    return ExportResult(
        source_path=source,
        destination_path=working_dest,
        bytes_written=working_dest.stat().st_size,
        converted_to_jpeg=converted,
        warnings=warnings,
        success=True,
    )


def _write_stripped(source: Path, dest: Path, src_format: ImageFormat) -> ExportResult:
    """Copy the image with all metadata removed."""
    import piexif
    from PIL import Image

    warnings: list[str] = []
    if src_format in _EXIF_NATIVE:
        shutil.copy2(source, dest)
        try:
            piexif.remove(str(dest))
        except Exception as exc:  # noqa: BLE001
            raise MetadataWriteError(
                f"Failed to strip metadata: {exc}",
                user_message="Metadata could not be removed from the copy.",
            ) from exc
    else:
        # Re-encode without any metadata (recompresses).
        with Image.open(source) as img:
            clean = Image.new(img.mode, img.size)
            clean.putdata(list(img.getdata()))
            clean.save(dest)
        warnings.append("Image was re-encoded to strip metadata, which may change compression.")
    return ExportResult(
        source_path=source,
        destination_path=dest,
        bytes_written=dest.stat().st_size,
        warnings=warnings,
        success=True,
    )


def _convert_to_jpeg(source: Path, dest: Path) -> tuple[Path, bool, str | None]:
    """Convert ``source`` to a JPEG at ``dest`` (extension forced to .jpg)."""
    from PIL import Image

    jpeg_dest = dest.with_suffix(".jpg")
    try:
        with Image.open(source) as img:
            rgb = img.convert("RGB")
            rgb.save(jpeg_dest, format="JPEG", quality=95, subsampling=0)
    except Exception as exc:  # noqa: BLE001
        raise MetadataWriteError(
            f"Conversion to JPEG failed: {exc}",
            user_message="The image could not be converted to JPEG.",
        ) from exc
    return (
        jpeg_dest,
        True,
        "Image was converted to JPEG to store metadata; this recompresses pixels.",
    )
