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


def _precise_rational(value: float, max_denominator: int = 1_000_000) -> tuple[int, int]:
    """Convert a float to the closest exact rational (num, denom).

    Used for exposure fields (e.g. shutter speeds like 1/121 s) where a fixed
    denominator would lose precision that a fixed-point one wouldn't.
    """
    from fractions import Fraction

    frac = Fraction(value).limit_denominator(max_denominator)
    return (frac.numerator, frac.denominator or 1)


def _has_exif_data(exif: dict) -> bool:
    """True if a piexif-style dict actually carries any tags to preserve."""
    return any(exif.get(key) for key in ("0th", "Exif", "GPS", "1st", "Interop"))


def _signed_rational(value: float, denom: int = 1000) -> tuple[int, int]:
    """Encode a signed float as an EXIF SRational (num, denom)."""
    from fractions import Fraction

    frac = Fraction(value).limit_denominator(denom)
    return (frac.numerator, frac.denominator or 1)


def _apply_exposure_fields(exif_ifd: dict, plan: ChangePlan) -> None:
    """Write the resolved exposure fields, including derived APEX values.

    All values come from ``plan.resolved_exposure`` (computed by the engine from
    the selected mode/profile/custom values and the source). PRESERVE leaves the
    source's values untouched via the base EXIF copy — nothing is invented from a
    device preset. ApertureValue is derived from the lens FNumber and
    ShutterSpeedValue from the exposure time (both APEX / log2 quantities).
    """
    import piexif

    from core.exposure.calculations import aperture_value_apex, shutter_speed_value_apex

    resolved = plan.resolved_exposure
    if resolved is None:
        return

    if resolved.iso is not None:
        exif_ifd[piexif.ExifIFD.ISOSpeedRatings] = int(resolved.iso)
    if resolved.exposure_time_seconds is not None:
        exif_ifd[piexif.ExifIFD.ExposureTime] = _precise_rational(resolved.exposure_time_seconds)
        # ShutterSpeedValue (APEX, signed) = -log2(exposureTime).
        ssv = shutter_speed_value_apex(resolved.exposure_time_seconds)
        exif_ifd[piexif.ExifIFD.ShutterSpeedValue] = _signed_rational(ssv)
    if resolved.exposure_bias is not None:
        exif_ifd[piexif.ExifIFD.ExposureBiasValue] = _signed_rational(resolved.exposure_bias)
    if resolved.flash is not None:
        exif_ifd[piexif.ExifIFD.Flash] = int(resolved.flash)
    if resolved.exposure_program is not None:
        exif_ifd[piexif.ExifIFD.ExposureProgram] = int(resolved.exposure_program)
    if resolved.metering_mode is not None:
        exif_ifd[piexif.ExifIFD.MeteringMode] = int(resolved.metering_mode)
    if resolved.white_balance is not None:
        exif_ifd[piexif.ExifIFD.WhiteBalance] = int(resolved.white_balance)
    if resolved.exposure_mode_exif is not None:
        exif_ifd[piexif.ExifIFD.ExposureMode] = int(resolved.exposure_mode_exif)
    if resolved.scene_capture_type is not None:
        exif_ifd[piexif.ExifIFD.SceneCaptureType] = int(resolved.scene_capture_type)
    if resolved.light_source is not None:
        exif_ifd[piexif.ExifIFD.LightSource] = int(resolved.light_source)

    # ApertureValue (APEX) is derived from the lens FNumber when one is known.
    if plan.f_number is not None and plan.f_number > 0:
        av = aperture_value_apex(plan.f_number)
        exif_ifd[piexif.ExifIFD.ApertureValue] = _precise_rational(av)


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


def _build_exif_dict(base: dict, plan: ChangePlan, out_dims: tuple[int, int] | None = None) -> dict:
    """Apply the change plan onto a piexif-style dict and return it.

    ``out_dims`` is the actual (width, height) of the written pixels; when given
    it is stamped into the EXIF pixel-dimension tags so they always match.
    """
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

    # EXIF pixel dimensions must match the actual written image dimensions.
    if out_dims is not None:
        width, height = out_dims
        exif_ifd[piexif.ExifIFD.PixelXDimension] = int(width)
        exif_ifd[piexif.ExifIFD.PixelYDimension] = int(height)

    # Lens fields (LensModel plus any optical values the preset supplied).
    _apply_lens_fields(exif_ifd, plan)

    # Exposure fields (ISO/shutter/EV) — only touched when explicitly requested;
    # otherwise whatever the source had already survives via the base copy.
    _apply_exposure_fields(exif_ifd, plan)

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

    resize = plan.resolution is not None and plan.resolution.changes_dimensions

    # A resize (or an explicit/needed JPEG conversion) means we must re-encode.
    force_jpeg = (plan.convert_to_jpeg and src_format != ImageFormat.JPEG) or resize
    if src_format in _EXIF_NATIVE and not force_jpeg:
        working_dest = dest
    elif src_format in _CONVERTIBLE or force_jpeg:
        if resize and plan.resolution is not None:
            from core.imaging.resize import load_and_resize

            working_dest = dest.with_suffix(".jpg")
            load_and_resize(source, plan.resolution, working_dest)
            converted = True
            if src_format != ImageFormat.JPEG:
                warnings.append(
                    "Image was converted to JPEG to store metadata; this recompresses pixels."
                )
            warnings.append(
                "Image pixel dimensions were changed. This does not restore real "
                "detail that was absent from the source."
            )
        else:
            working_dest, converted, warn = _convert_to_jpeg(source, dest)
            if warn:
                warnings.append(warn)
        # HEIF sources carry real camera EXIF (ISO, shutter, lens…) that Pillow
        # can read; only PNG/WEBP genuinely have nothing to preserve. Losing
        # HEIF's base_exif here was silently discarding all of that data.
        if not _has_exif_data(base_exif):
            base_exif = _empty_exif()
    else:
        raise UnsupportedImageFormatError(
            f"Cannot write metadata for format {src_format}",
            user_message="This image format is not supported for metadata writing.",
        )

    if not converted:
        shutil.copy2(source, working_dest)

    out_dims = _read_dimensions(working_dest)
    exif_dict = _build_exif_dict(base_exif, plan, out_dims)
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


def _read_dimensions(path: Path) -> tuple[int, int]:
    """Return the (width, height) of the written image."""
    from PIL import Image

    with Image.open(path) as img:
        return img.size


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
    """Convert ``source`` to a JPEG at ``dest`` (extension forced to .jpg).

    Never resizes: the source is decoded at full resolution and only the pixel
    format/encoding changes. No ``thumbnail()`` or other downscaling is used.
    """
    from PIL import Image

    jpeg_dest = dest.with_suffix(".jpg")
    try:
        with Image.open(source) as img:
            src_size = img.size
            rgb = img.convert("RGB")
            if rgb.size != src_size:
                raise MetadataWriteError(
                    f"Format conversion changed dimensions: {src_size} -> {rgb.size}",
                    user_message=(
                        "The image could not be converted without changing its resolution."
                    ),
                )
            rgb.save(jpeg_dest, format="JPEG", quality=95, subsampling=0)
    except MetadataWriteError:
        raise
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
