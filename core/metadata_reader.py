"""Read image metadata into a typed :class:`MetadataSummary`.

Reading is best-effort and format-aware. JPEG/TIFF use piexif for full EXIF.
Other formats fall back to Pillow's decoded EXIF where available. Nothing here
mutates the source file.
"""

from __future__ import annotations

from pathlib import Path

from core.exceptions import CorruptImageError, MetadataReadError, UnsupportedImageFormatError
from core.gps import dms_rational_to_decimal
from core.metadata_models import ImageFormat, MetadataSummary

# Optional HEIF support: registers a Pillow opener when installed.
try:  # pragma: no cover - depends on optional dependency
    import pillow_heif

    pillow_heif.register_heif_opener()
    _HEIF_AVAILABLE = True
except Exception:  # noqa: BLE001
    _HEIF_AVAILABLE = False


_PIL_FORMAT_MAP = {
    "JPEG": ImageFormat.JPEG,
    "MPO": ImageFormat.JPEG,
    "TIFF": ImageFormat.TIFF,
    "PNG": ImageFormat.PNG,
    "WEBP": ImageFormat.WEBP,
    "HEIF": ImageFormat.HEIF,
    "HEIC": ImageFormat.HEIF,
}


def detect_format(path: Path) -> ImageFormat:
    """Detect the image format from content (not just extension)."""
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(path) as img:
            return _PIL_FORMAT_MAP.get(img.format or "", ImageFormat.UNKNOWN)
    except UnidentifiedImageError:
        return ImageFormat.UNKNOWN
    except FileNotFoundError as exc:
        raise MetadataReadError(
            f"File not found: {path}", user_message="The image file could not be found."
        ) from exc


def read_summary(path: Path) -> MetadataSummary:
    """Read a full :class:`MetadataSummary` for ``path``."""
    from PIL import Image, UnidentifiedImageError

    path = Path(path)
    try:
        with Image.open(path) as img:
            img_format = _PIL_FORMAT_MAP.get(img.format or "", ImageFormat.UNKNOWN)
            width, height = img.size
            exif_dict = _extract_exif_dict(path, img_format)
    except UnidentifiedImageError as exc:
        raise CorruptImageError(
            f"Cannot identify image: {path}",
            user_message="This file is not a recognised image or is corrupt.",
        ) from exc
    except FileNotFoundError as exc:
        raise MetadataReadError(
            f"File not found: {path}", user_message="The image file could not be found."
        ) from exc

    return _summary_from_exif(exif_dict, img_format, width, height)


def _extract_exif_dict(path: Path, img_format: ImageFormat) -> dict:
    """Return a piexif-style nested dict, or ``{}`` if none/unsupported."""
    if img_format in (ImageFormat.JPEG, ImageFormat.TIFF):
        import piexif

        try:
            return piexif.load(str(path))
        except Exception as exc:  # noqa: BLE001 - piexif raises broad errors
            raise MetadataReadError(
                f"Failed to parse EXIF from {path}: {exc}",
                user_message="The image's EXIF metadata could not be read.",
            ) from exc
    # PNG/WEBP/HEIF: use Pillow's exif if present (may be empty).
    from PIL import Image

    try:
        with Image.open(path) as img:
            exif = img.getexif()
    except Exception:  # noqa: BLE001
        return {}
    if not exif:
        return {}
    # Normalise into the same nested shape piexif uses (0th + Exif + GPS).
    return _pillow_exif_to_piexif_shape(exif)


#: 0th-IFD tags that are internal IFD offset pointers, not real metadata.
#: Carrying a stale value forward would conflict with what piexif recomputes.
_IFD_POINTER_TAGS = {34665, 34853}  # ExifTag, GPSTag


def _normalize_piexif_value(ifd_name: str, tag_id: int, value):
    """Coerce a Pillow-decoded EXIF value into the type piexif expects.

    Pillow's ``Image.getexif()``/``get_ifd()`` return plain ``str``/``int``/
    ``float`` (e.g. ``FocalLength`` as ``5.7``), while piexif requires
    ``bytes`` for ASCII tags and ``(numerator, denominator)`` tuples for
    Rational/SRational tags. Without this, values read from a HEIF source are
    silently unusable (dropped as "not a tuple") or make ``piexif.dump()``
    raise when the value is later written back out.
    """
    import piexif
    from piexif import TYPES

    tag_info = piexif.TAGS.get(ifd_name, {}).get(tag_id)
    if tag_info is None:
        return value
    tag_type = tag_info["type"]
    if tag_type == TYPES.Ascii:
        return value.encode("utf-8") if isinstance(value, str) else value
    if tag_type in (TYPES.Rational, TYPES.SRational):
        if isinstance(value, tuple):
            return value
        # Pillow's TiffImagePlugin.IFDRational (from get_ifd()) isn't a tuple,
        # int, or float, but it does carry numerator/denominator directly.
        if hasattr(value, "numerator") and hasattr(value, "denominator"):
            denom = int(value.denominator) or 1
            return (int(value.numerator), denom)
        if isinstance(value, (int, float)):
            from fractions import Fraction

            frac = Fraction(value).limit_denominator(1_000_000)
            return (frac.numerator, frac.denominator or 1)
        return value
    if tag_type in (TYPES.Short, TYPES.Long, TYPES.SShort, TYPES.SLong, TYPES.Byte, TYPES.SByte):
        return int(round(value)) if isinstance(value, float) else value
    return value


def _pillow_exif_to_piexif_shape(exif) -> dict:
    """Best-effort conversion of a Pillow Exif mapping to piexif's nested dict."""
    import piexif
    from PIL.ExifTags import IFD

    result: dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "Interop": {}, "thumbnail": None}
    for tag_id, value in exif.items():
        if tag_id in piexif.TAGS["0th"] and tag_id not in _IFD_POINTER_TAGS:
            result["0th"][tag_id] = _normalize_piexif_value("0th", tag_id, value)
    try:
        exif_ifd = exif.get_ifd(IFD.Exif)
        for tag_id, value in exif_ifd.items():
            result["Exif"][tag_id] = _normalize_piexif_value("Exif", tag_id, value)
    except Exception:  # noqa: BLE001
        pass
    try:
        gps_ifd = exif.get_ifd(IFD.GPSInfo)
        for tag_id, value in gps_ifd.items():
            result["GPS"][tag_id] = _normalize_piexif_value("GPS", tag_id, value)
    except Exception:  # noqa: BLE001
        pass
    return result


def _decode(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").rstrip("\x00").strip() or None
    return str(value).strip() or None


def _summary_from_exif(
    exif: dict, img_format: ImageFormat, width: int, height: int
) -> MetadataSummary:
    import piexif

    zeroth = exif.get("0th", {}) if exif else {}
    exif_ifd = exif.get("Exif", {}) if exif else {}
    gps_ifd = exif.get("GPS", {}) if exif else {}

    def z(tag: int):
        return _decode(zeroth.get(tag))

    def e(tag: int):
        return _decode(exif_ifd.get(tag))

    def rat(tag: int) -> str | None:
        """Format an EXIF rational (num, denom) as a decimal string."""
        val = exif_ifd.get(tag)
        if isinstance(val, tuple) and len(val) == 2 and val[1]:
            return f"{val[0] / val[1]:g}"
        if isinstance(val, (int, float)):
            return f"{val:g}"
        return None

    def shutter(tag: int) -> str | None:
        """Format an exposure time rational as Apple Photos would (e.g. '1/121')."""
        val = exif_ifd.get(tag)
        num = denom = None
        if isinstance(val, tuple) and len(val) == 2 and val[1]:
            num, denom = val
        elif isinstance(val, (int, float)) and val > 0:
            num, denom = 1, round(1 / val)
        if not num:
            return None
        seconds = num / denom
        if seconds < 1 and num != 0:
            inverse = round(denom / num)
            return f"1/{inverse}" if inverse else f"{seconds:g}"
        return f"{seconds:g}"

    def iso() -> int | None:
        val = exif_ifd.get(piexif.ExifIFD.ISOSpeedRatings)
        if isinstance(val, tuple):
            val = val[0] if val else None
        try:
            return int(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    def short(tag: int) -> int | None:
        """Decode an EXIF SHORT/LONG enumerated value as an int."""
        val = exif_ifd.get(tag)
        if isinstance(val, tuple):
            val = val[0] if val else None
        try:
            return int(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    lat, lon, alt = _gps_from_ifd(gps_ifd)

    raw: dict[str, str] = {}
    for name, ifd in (("0th", zeroth), ("Exif", exif_ifd), ("GPS", gps_ifd)):
        for tag_id, value in ifd.items():
            decoded = _decode(value)
            if decoded is not None and len(decoded) <= 256:
                raw[f"{name}:{tag_id}"] = decoded

    return MetadataSummary(
        image_format=img_format,
        width=width,
        height=height,
        make=z(piexif.ImageIFD.Make),
        model=z(piexif.ImageIFD.Model),
        software=z(piexif.ImageIFD.Software),
        lens_model=e(piexif.ExifIFD.LensModel),
        focal_length=rat(piexif.ExifIFD.FocalLength),
        f_number=rat(piexif.ExifIFD.FNumber),
        focal_length_35mm=rat(piexif.ExifIFD.FocalLengthIn35mmFilm),
        iso=iso(),
        exposure_time=shutter(piexif.ExifIFD.ExposureTime),
        exposure_bias=rat(piexif.ExifIFD.ExposureBiasValue),
        aperture_value=rat(piexif.ExifIFD.ApertureValue),
        shutter_speed_value=rat(piexif.ExifIFD.ShutterSpeedValue),
        flash=short(piexif.ExifIFD.Flash),
        exposure_program=short(piexif.ExifIFD.ExposureProgram),
        metering_mode=short(piexif.ExifIFD.MeteringMode),
        white_balance=short(piexif.ExifIFD.WhiteBalance),
        exposure_mode=short(piexif.ExifIFD.ExposureMode),
        scene_capture_type=short(piexif.ExifIFD.SceneCaptureType),
        light_source=short(piexif.ExifIFD.LightSource),
        exif_image_width=short(piexif.ExifIFD.PixelXDimension),
        exif_image_height=short(piexif.ExifIFD.PixelYDimension),
        datetime_original=e(piexif.ExifIFD.DateTimeOriginal),
        create_date=e(piexif.ExifIFD.DateTimeDigitized),
        modify_date=z(piexif.ImageIFD.DateTime),
        offset_time_original=e(piexif.ExifIFD.OffsetTimeOriginal),
        gps_latitude=lat,
        gps_longitude=lon,
        gps_altitude_m=alt,
        has_gps=lat is not None and lon is not None,
        raw_tags=raw,
    )


def _gps_from_ifd(gps_ifd: dict):
    """Extract (lat, lon, alt) decimals from a piexif GPS IFD, or (None, None, None)."""
    import piexif

    lat = lon = alt = None
    try:
        if piexif.GPSIFD.GPSLatitude in gps_ifd and piexif.GPSIFD.GPSLatitudeRef in gps_ifd:
            ref = _decode(gps_ifd[piexif.GPSIFD.GPSLatitudeRef]) or "N"
            lat = dms_rational_to_decimal(tuple(gps_ifd[piexif.GPSIFD.GPSLatitude]), ref)
        if piexif.GPSIFD.GPSLongitude in gps_ifd and piexif.GPSIFD.GPSLongitudeRef in gps_ifd:
            ref = _decode(gps_ifd[piexif.GPSIFD.GPSLongitudeRef]) or "E"
            lon = dms_rational_to_decimal(tuple(gps_ifd[piexif.GPSIFD.GPSLongitude]), ref)
        if piexif.GPSIFD.GPSAltitude in gps_ifd:
            num, denom = gps_ifd[piexif.GPSIFD.GPSAltitude]
            alt = num / denom if denom else None
            if gps_ifd.get(piexif.GPSIFD.GPSAltitudeRef, 0) == 1 and alt is not None:
                alt = -alt
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None, None, None
    return lat, lon, alt


def is_supported(path: Path) -> bool:
    """Return True if the engine can at least read this format."""
    fmt = detect_format(Path(path))
    if fmt == ImageFormat.HEIF and not _HEIF_AVAILABLE:
        raise UnsupportedImageFormatError(
            "HEIF support not installed",
            user_message="HEIC/HEIF support requires the optional 'pillow-heif' package.",
        )
    return fmt != ImageFormat.UNKNOWN
