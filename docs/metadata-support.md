# Metadata & format support

This document states the **actual** support level per format. Where something is
not implemented, it is listed as not implemented rather than implied to work.

## Format matrix

| Format | Read | Write EXIF | Pixel preservation | Export behaviour | Known limitations |
|--------|:----:|:----------:|:------------------:|------------------|-------------------|
| JPEG/JPG | ✅ full (piexif) | ✅ | ✅ EXIF-only edit, no recompression | Copy + insert EXIF | — |
| TIFF | ✅ full (piexif) | ✅ | ✅ | Copy + insert EXIF | Less exercised than JPEG. |
| HEIC/HEIF | ⚠️ read only, requires optional `pillow-heif` | ❌ not implemented | — | Offer JPEG conversion for writing | **Do not** assume HEIC metadata writing works. |
| PNG | ✅ basic (Pillow) | ⚠️ only via JPEG conversion | ❌ recompresses on convert | Convert to JPEG (warned) | PNG has no native EXIF like JPEG. |
| WebP | ✅ basic (Pillow) | ⚠️ only via JPEG conversion | ❌ recompresses on convert | Convert to JPEG (warned) | — |

When the selected format cannot reliably store the requested fields, the engine
converts to JPEG and records a warning that conversion changes the encoding.

## Supported EXIF fields

Written by the engine (JPEG/TIFF):

| Field | IFD | Notes |
|-------|-----|-------|
| `Make` | 0th | From preset manufacturer or manual. |
| `Model` | 0th | From preset `exif_model`. |
| `Software` | 0th | Optional. |
| `LensModel` | Exif | Only written when a preset provides a value. |
| `DateTimeOriginal` | Exif | Capture time. |
| `DateTimeDigitized` (`CreateDate`) | Exif | Set alongside original. |
| `DateTime` (`ModifyDate`) | 0th | Set alongside original. |
| `OffsetTime` / `OffsetTimeOriginal` / `OffsetTimeDigitized` | Exif | `+HH:MM`. |
| `GPSLatitude` / `GPSLatitudeRef` | GPS | Rational DMS + N/S. |
| `GPSLongitude` / `GPSLongitudeRef` | GPS | Rational DMS + E/W. |
| `GPSAltitude` / `GPSAltitudeRef` | GPS | Optional; ref 0 above / 1 below sea level. |

## Preset data honesty

- iPhone `exif_model` strings for the iPhone 11–16 families are treated as
  verified (`source_status: "verified"`).
- iPhone 16e, iPhone Air, and the iPhone 17 family are `placeholder` until their
  exact EXIF `Model` strings are confirmed on real devices.
- Lens entries carry friendly display names ("Main Camera", "Ultra Wide
  Camera", …) but empty `lens_model` — precise Apple lens EXIF values are **not**
  invented. A lens value is only written when a preset explicitly provides one.

## Authenticity

Metadata is user-editable. LensTrace Studio makes editing transparent (preview +
confirm + optional audit sidecar) but nothing about stored metadata proves the
real capture conditions of an image.
