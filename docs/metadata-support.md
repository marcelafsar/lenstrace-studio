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

## Lens metadata (LensModel and optical fields)

A selected lens has three distinct concepts — do not confuse them:

| Concept | Example | Notes |
|---------|---------|-------|
| Friendly lens (UI only) | `Main Camera` | Never written to EXIF. |
| EXIF `LensModel` | `Apple iPhone 13 Pro Max Main Camera` | Always written when a lens is selected. |
| `FocalLength` / `FNumber` / `FocalLengthIn35mmFilm` / `LensSpecification` | 6.86 mm, f/1.78, 26 mm | Written **only** when a preset supplies verified values. |

How `LensModel` is resolved (`core/presets/lens_resolver.py`):

- If a preset provides a verified `lens_model`, that exact value is written.
- Otherwise a **transparent generic fallback** is generated —
  `"{manufacturer} {exif_model} {lens_display_name}"` (e.g. *Apple iPhone 13 Pro
  Max Main Camera*) — and marked `source: "generic"`. This is never presented as
  verified original Apple metadata; the review screen labels it *(generic)*.
- Optical values are **never invented**. Missing focal length / aperture simply
  stay unset; a stale focal length from a different lens is cleared when a new
  lens is applied.
- "Keep original lens" preserves existing lens fields; "Remove lens" clears them.

After writing, the engine **reads the file back and verifies** the requested
fields. A requested `LensModel` that is missing from the output is a hard export
failure — the bots refuse to send such a file and surface an error instead.

### Why JPEG for Apple Photos

PNG/WebP EXIF is not reliably displayed by Apple Photos. On export the engine
converts these formats to JPEG (recompressing, with a warning) so `LensModel`
and other EXIF are broadly visible; the original file is never modified. JPEG is
the recommended output when the goal is metadata visibility in Apple Photos.

## Preset data honesty

- iPhone `exif_model` strings for the iPhone 11–16 families are treated as
  verified (`source_status: "verified"`).
- iPhone 16e, iPhone Air, and the iPhone 17 family are `placeholder` until their
  exact EXIF `Model` strings are confirmed on real devices.
- Lens entries carry friendly display names ("Main Camera", "Ultra Wide
  Camera", …). Where a preset leaves `lens_model` empty, a generic fallback is
  generated at resolve time (marked generic) so a selected lens is **never**
  written blank; precise Apple optical values are not invented.

## Authenticity

Metadata is user-editable. LensTrace Studio makes editing transparent (preview +
confirm + optional audit sidecar) but nothing about stored metadata proves the
real capture conditions of an image.
