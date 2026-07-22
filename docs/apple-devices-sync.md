# Apple Devices assisted sync

An **assisted** Windows workflow — not direct Camera Roll injection. LensTrace
copies the exact exported file into a local **LensTrace Sync** folder and guides
you to sync it with the Apple Devices app.

## What it does (implemented)

- Creates/uses a sync folder (default `%USERPROFILE%\Pictures\LensTrace Sync`,
  or `LENSTRACE_SYNC_PATH`, or a folder you pick).
- Copies the exact file and verifies size + SHA-256 + metadata.
- Best-effort, read-only detection of the Apple Devices / iTunes app.
- Offers: Open Apple Devices, Open the sync folder, copy instructions, recheck.
- Guided steps: connect by USB (or existing Wi-Fi sync), unlock, trust the
  computer, open Apple Devices, select the device, open Photos, choose the
  LensTrace Sync folder, apply/sync.

After a verified copy it reports *waiting for sync* and explains Apple Devices
controls the actual synchronisation.

## What it does NOT do

- No automation of the app, no keystrokes/UI automation, no clicking sync.
- No editing of Apple configuration/databases; no iCloud Photos toggling.
- Opening the app is **not** treated as a completed sync.
- The result is **not** a native Camera capture.

## Honest caveats

- Photos synced from a computer generally behave as **computer-synced** items in
  the iPhone's library, not Camera captures.
- Apple Devices photo-sync options may be **hidden when iCloud Photos is
  enabled**; LensTrace does not change that setting.
- App detection on Windows is unreliable (Apple Devices is a Store app); when
  detection is uncertain, LensTrace says *"Open Apple Devices to confirm the
  connected iPhone."*
- **Not tested against a real device** in this repository.
