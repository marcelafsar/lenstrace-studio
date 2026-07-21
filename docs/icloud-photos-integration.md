# iCloud Photos integration

Copies the exact exported file into the iCloud Photos upload location on Windows
so iCloud can sync it to your devices.

## What it does (implemented)

- Detects a likely iCloud Photos folder from known Windows locations
  (`%USERPROFILE%\iCloudPhotos`, `%USERPROFILE%\Pictures\iCloud Photos`, …) or a
  configured `ICLOUD_PHOTOS_PATH`. If the folder contains an `Uploads`
  subfolder, that is preferred.
- Lets you pick the destination folder manually (Electron folder dialog).
- Copies the exact file, then verifies size + SHA-256 + metadata.
- Resolves name collisions (`photo.jpg` → `photo (1).jpg`).
- Reports one of: detected / manual destination / copying / copy verified /
  waiting for iCloud / destination invalid / copy failed.

After a verified copy it states:
*"Copied to the iCloud Photos folder. Apple controls upload and synchronisation
status."* It never claims the file reached the iPhone.

## What it does NOT do

- No Apple Account login or automation; no access to Apple credentials.
- No scanning of the whole drive or unrelated iCloud documents.
- No guarantee that the file uploaded — that is Apple's responsibility.

## Browser fallback

When iCloud for Windows is not available you can open the official iCloud Photos
website (validated HTTPS URL only) and the LensTrace output folder, then upload
manually. LensTrace does not pass the local file path in a URL, does not
automate sign-in, and does not store Apple credentials. Opening the website does
not upload the file.

## Assumptions / limitations

- Folder auto-detection is best-effort; the exact path varies by iCloud version.
  Prefer selecting the folder manually if detection is wrong.
- **Not tested against a live iCloud account / iPhone** in this repository.
