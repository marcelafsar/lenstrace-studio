# Manual test checklist — Send to iPhone & bots

These require real accounts/devices and are **not** automated. Use a disposable
test image (never a personal photo). Record confirmed vs. assumed behaviour.

## iCloud Photos

1. Export a disposable JPEG in LensTrace.
2. Record its SHA-256 (shown in the integrity summary / audit sidecar).
3. Copy it through the iCloud Photos method.
4. Confirm the destination checksum is reported as verified.
5. Wait for iCloud to sync; inspect the image on the iPhone.
6. Record displayed metadata and any source/provenance wording.
7. If possible, download the original from iCloud and compare bytes + metadata.

## PairDrop

1. Put Windows and iPhone on the same network.
2. Export a disposable JPEG.
3. Open PairDrop through LensTrace; scan the QR on the iPhone.
4. Transfer the file; save via iOS.
5. Inspect metadata; record source/provenance wording.
6. Repeat with PairDrop installed as a PWA.
7. Record confirmed vs. assumed behaviour (e.g. relay usage).

## Apple Devices

1. Export a disposable JPEG; copy to LensTrace Sync; verify checksum.
2. Connect and trust the iPhone; open Apple Devices.
3. Select the device → Photos → choose the LensTrace Sync folder → sync.
4. Inspect behaviour on the iPhone.
5. Record whether iCloud Photos being enabled hides sync controls.
6. Record removal/resync behaviour.

## Bots

1. Configure Telegram in the Bots panel; test the token; start the bot.
2. Confirm status shows Running and the resolved @username.
3. Use `/start`, `/help`, and a metadata command.
4. Stop and restart; close LensTrace and confirm the child process stops.
5. Repeat for Discord (`/metadata` commands, command sync).
6. Test an invalid token (expect a clear error, no crash).
7. Confirm tokens never appear in logs, the UI, or the audit files.

## Expected honesty checks

- No method should be described as making the image a native Camera capture or
  as removing Apple provenance labels.
- "Completed"/"waiting for sync" must reflect only a verified local copy, never a
  guaranteed iPhone import.
