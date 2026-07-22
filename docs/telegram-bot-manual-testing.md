# Telegram bot — manual testing

A safe, token-free-in-output checklist for verifying the Telegram bot end to end.
Configure the token in the desktop **Bots** panel (or `.env`); it is never
printed. Use a disposable test image, never a personal photo.

## Enable detailed logs

Set `LOG_LEVEL=DEBUG` (Bots panel picks up the configured level). The Bot Control
Center shows redacted logs and structured readiness (Authenticated → Polling
ready). Child stdout is unbuffered so events appear promptly.

## Checklist

1. Start the Telegram bot through LensTrace (Bots → Telegram → Start).
2. Wait until the panel shows **Authenticated** and **Polling ready** (green).
   Until then it shows *Starting…*, not a green "Running".
3. In Telegram, run `/start` — expect the welcome message.
4. Send a PNG **as a compressed photo** — expect the warning with buttons
   (*Continue with this photo* / *I'll send it as a file* / *Cancel*).
5. Send the same PNG **as a file/document** — expect an immediate
   "📥 File received. Inspecting metadata…", then a metadata summary with action
   buttons (Edit / Inspect / Remove / Cancel). *(This is the path that was
   previously silent; it now works for image/png AND application/octet-stream.)*
6. Tap **Inspect** — expect the original metadata.
7. Tap **Edit** → choose a device generation → model → lens → date option →
   time zone → location option → **Review** → **Confirm & export**.
8. Receive the processed file back **as a document** (not a recompressed photo),
   plus the audit sidecar JSON.
9. Download and inspect the result; confirm the requested changes are present and
   the original is unchanged.
10. Start another edit and use `/cancel` — confirm the session clears.
11. Send a non-image file (e.g. a `.txt`) — expect a clear "not supported"
    message, no crash.
12. Send a corrupt/renamed file (`.png` containing non-image bytes) — expect a
    friendly error, no silent failure.
13. Confirm no token appears anywhere in the logs, UI, or audit files.
14. Confirm a subsequent upload still works without restarting the bot.

## What to record

- Confirmed vs. assumed behaviour for each step.
- Whether the acknowledgement appears before inspection.
- That errors are visible both to the user and in the redacted logs.

## Lens, address search, and date pickers (this session)

### Lens metadata (the reported bug)

1. Send a JPEG as a document → **Edit** → device **Apple iPhone 13 Pro Max**.
2. Choose **Main Camera** → keep date → skip location → **Review**.
3. The review must show `Lens model: Apple iPhone 13 Pro Max Main Camera` (marked
   *(generic)* since no verified optical values exist).
4. Confirm & export; open the returned document in a metadata viewer and confirm
   **LensModel is present** (not blank). Repeat for **Ultra Wide** and
   **Telephoto**.
5. Send a **PNG** as a document and edit it — the returned file is a **JPEG**
   (for Apple Photos EXIF visibility) with the LensModel present.

### Address search

1. In the edit flow reach **Location → 🔍 Search by address**.
2. Enter e.g. `Sultanahmet, Istanbul` → expect "Searching…" then a list of
   results as buttons.
3. Tap a result → expect its full address, coordinates, a map link, and a shared
   Telegram location preview, with **Use this location / Search again / Enter
   coordinates / Remove / Cancel**.
4. **Search again** with a different query → new results.
5. **Use this location** → returns to review with GPS set. Confirm export writes
   GPS.
6. **Enter coordinates** manually (e.g. `41.0082, 28.9784`) still works, with a
   map link preview.

### Date/time picker

1. **Date & time → 📅 Choose from calendar** → navigate months → pick a day.
2. Choose hour → minute (or **Custom**) → time zone.
3. Review shows the date/time and UTC offset; confirm it is written to EXIF
   (`DateTimeOriginal` + `OffsetTimeOriginal`).
4. **Enter manually** (`YYYY-MM-DD HH:MM:SS`) still works and rejects impossible
   values (e.g. `2026-02-30`, `25:00`).
