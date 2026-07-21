# Send to iPhone — delivery methods

LensTrace edits the metadata *embedded in an image file*. After you export a
copy, the **Send to iPhone** screen offers three ways to move that exact file
toward an iPhone. LensTrace preserves the file bytes and embedded metadata; it
does **not** control what Apple or a transfer service records about the imported
asset.

## What LensTrace can and cannot do

**Can:** preserve the exact exported bytes and EXIF; copy the file to supported
Windows destinations; open supported apps/websites; prepare folders for
user-controlled sync; verify SHA-256 and metadata; report progress honestly.

**Cannot / does not:** make an imported image a genuine iPhone Camera capture;
remove or alter Apple's "Imported"/"Synced from computer"/"Saved from…" source
labels; write into the iPhone Photos database; inject into DCIM; bypass Apple
security; or prove that selected EXIF reflects the real capture device, place,
date, or lens. Metadata is editable and does not prove capture facts.

## Comparison

| Method | Requirements | Automatic? | Main limitation |
|--------|--------------|------------|-----------------|
| iCloud Photos | iCloud for Windows + iCloud Photos | Copy-assisted | Apple controls sync/provenance |
| PairDrop | A modern browser (both devices) | User transfer | iOS performs the final save |
| Apple Devices | Apple Devices app + cable/Wi-Fi | Assisted sync | Behaves as computer-synced photos |

## Shared integrity guarantees

For every method LensTrace:

1. Records the export's filename, format, MIME, dimensions, size, SHA-256, and
   key EXIF (Make/Model/LensModel/DateTimeOriginal/OffsetTimeOriginal/GPS
   presence) before delivery.
2. Copies raw bytes only (`shutil.copy2`) — never decodes/re-encodes, never uses
   Pillow for the copy, never rewrites metadata.
3. Verifies the destination copy by size + SHA-256, and re-checks the metadata
   summary.
4. Removes an incomplete destination copy if verification fails.
5. Handles spaces and Unicode filenames; resolves collisions Explorer-style
   (`photo.jpg` → `photo (1).jpg`).

Filesystem timestamps (created/modified) are distinct from embedded EXIF and are
set by the OS/copy, not by LensTrace's metadata editor.

## Status

Implemented and unit-tested: integrity capture, verified copy, collision
handling, URL validation, provider availability, and the prepare/execute
lifecycle. **Not verified on a real iPhone** in this repository — see
[iphone-delivery-manual-testing.md](iphone-delivery-manual-testing.md).
