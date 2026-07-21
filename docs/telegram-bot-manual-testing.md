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
