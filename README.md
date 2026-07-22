<!-- Logo placeholder — replace docs/screenshots/logo.png with a real asset. -->
<p align="center">
  <!-- ![LensTrace Studio](docs/screenshots/logo.png) -->
  <strong>LensTrace Studio</strong>
</p>

<p align="center">
  A professional photo-metadata editor with a Windows desktop app plus Telegram
  and Discord bots — all built on one shared Python engine.
</p>

<!-- Badge placeholders — wire these up once the repository is public.
[![CI](placeholder)](placeholder) [![License: MIT](placeholder)](LICENSE)
-->

---

> ⚠️ **Metadata authenticity disclaimer.** Image metadata (EXIF/GPS/timestamps)
> is fully user-editable and does **not** prove when, where, or how a photo was
> actually captured. LensTrace Studio is for legitimate metadata management,
> testing, organisation, privacy, and educational purposes. Every export is a
> **new copy** — your originals are never modified.

## What it does

- Inspect the original metadata stored in an image.
- Apply a device identity (Apple iPhone presets), camera/lens info, capture
  date/time with time zone & UTC offset, and optional GPS coordinates.
- Preview a before/after diff and confirm before anything is written.
- Export a modified copy to a separate output folder, with an optional JSON
  **audit sidecar** recording exactly what changed.
- Remove all metadata.
- Batch-process multiple images (desktop).
- **Send an exported copy toward an iPhone** (iCloud Photos, PairDrop, or Apple
  Devices assisted sync) with byte-for-byte + metadata verification.
- **Set up and supervise the Telegram/Discord bots** from a desktop panel.
- **Check your environment** from a CLI or the Diagnostics panel.

## Send to iPhone

After exporting, the **Send to iPhone** screen offers three ways to move the
exact file toward an iPhone. LensTrace preserves the file bytes and embedded
metadata and verifies every copy by SHA-256; **Apple and external services
control final import behaviour and any source/provenance labels**. See
[docs/iphone-delivery-methods.md](docs/iphone-delivery-methods.md).

| Method | Requirements | Automatic? | Main limitation |
|--------|--------------|------------|-----------------|
| iCloud Photos | iCloud for Windows | Copy-assisted | Apple controls sync/provenance |
| PairDrop | Modern browsers | User transfer | iOS performs the final save |
| Apple Devices | Apple Devices + cable/Wi-Fi | Assisted sync | Computer-synced behaviour |

> LensTrace does **not** make an image a native Camera capture, hide import
> source, remove provenance, or inject into the Camera Roll. Metadata is editable
> and does not prove when, where, or with which device a photo was captured.

## Bot Control Center

The desktop **Bots** panel configures and supervises the Telegram and Discord
bots — token setup wizard (test/save, never shown again after saving),
start/stop/restart, auto-start, live status, and redacted logs. Bots run as
supervised child processes, are disabled by default, and stop when LensTrace
closes. See [docs/bot-control-center.md](docs/bot-control-center.md).

## Quick environment check

```powershell
python scripts/check_env.py
```

Shows `[PASS]`/`[WARN]`/`[FAIL]` lines. Options: `--service`, `--json`,
`--strict`, `--connectivity`. Exit codes: `0` all required pass, `1` a required
check failed, `2` configuration invalid, `3` checker error. No secret is ever
printed. See [docs/environment-checker.md](docs/environment-checker.md).

## Three interfaces, one engine

| Interface | Status | Notes |
|-----------|--------|-------|
| Windows desktop (Electron + React + Vite) | **MVP working** | Talks only to a local `127.0.0.1` backend with a per-session token. |
| Telegram bot (`python-telegram-bot`) | Scaffold, not run in CI | Imports the same engine; handler logic unit-tested with mocks. |
| Discord bot (`discord.py`) | Scaffold, not run in CI | Slash commands, buttons, select menus, modals. |

All three call the same `core.MetadataEngine`. Metadata-writing logic lives in
`core/` only — never duplicated in a UI or bot handler.

## Supported formats

Actual, tested support levels — see [docs/metadata-support.md](docs/metadata-support.md):

| Format | Read | Write EXIF | Preserves pixels | Notes |
|--------|:----:|:----------:|:----------------:|-------|
| JPEG/JPG | ✅ | ✅ | ✅ (EXIF-only edit) | Primary, fully tested. |
| HEIC/HEIF | ⚠️ read only* | ❌ | — | Read needs optional `pillow-heif`. Writing is **not** implemented. |
| TIFF | ✅ | ✅ | ✅ | Supported via piexif. |
| PNG | ✅ | ⚠️ via convert | ❌ (recompresses) | Offered as JPEG conversion. |
| WebP | ✅ | ⚠️ via convert | ❌ (recompresses) | Offered as JPEG conversion. |

\* HEIC/HEIF metadata **writing** is deliberately not claimed as supported. When
a format cannot store the requested fields, the app offers JPEG conversion and
warns that conversion recompresses pixels.

## Architecture (short version)

```
core/      shared metadata engine (models, validation, gps, datetime, presets, reader/writer, audit)
backend/   local FastAPI API (127.0.0.1, ephemeral port, session-token auth) — desktop only
desktop/   Electron + React + Vite + TypeScript frontend
bots/      shared session/temp/format helpers + telegram_bot + discord_bot
tests/     pytest suite (engine, presets, gps, datetime, validation, api, bots)
```

See [docs/architecture.md](docs/architecture.md) for the full picture.

## Development setup (Windows PowerShell)

Requires **Python 3.12+** (the core also runs on 3.10/3.11) and **Node.js 18+**.

```powershell
git clone <repository-url>
cd lenstrace-studio

py -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

cd desktop
npm install
cd ..

python run_desktop.py
```

`run_desktop.py` validates dependencies, picks a free loopback port, generates a
session token, starts the backend, waits for it to be healthy, then launches the
Electron app — and shuts everything down cleanly on exit or Ctrl+C.

## Bot setup

You can configure bots two ways:

- **Desktop Bot Control Center** (recommended) — paste, test, and save the token
  in the Bots panel. The saved token is stored securely and **never shown again**
  (only a masked suffix). See [docs/bot-control-center.md](docs/bot-control-center.md),
  [docs/telegram-bot-setup.md](docs/telegram-bot-setup.md), and
  [docs/discord-bot-setup.md](docs/discord-bot-setup.md).
- **Environment variables** (source mode) — see [docs/bot-setup.md](docs/bot-setup.md):

```powershell
Copy-Item .env.example .env   # then fill in the token(s)
.\scripts\run_telegram_bot.ps1
.\scripts\run_discord_bot.ps1
```

### Bot controls

The Bots panel provides start / stop / restart, an auto-start toggle, redacted
logs, and clear-token. Bots run as supervised child processes: disabled by
default, no automatic startup unless you opt in, and stopped when LensTrace
closes. See [docs/bot-process-supervision.md](docs/bot-process-supervision.md).

### Environment variables

| Variable | Purpose |
|----------|---------|
| `TELEGRAM_BOT_ENABLED` / `TELEGRAM_BOT_TOKEN` / `TELEGRAM_BOT_AUTO_START` | Telegram bot config. |
| `DISCORD_BOT_ENABLED` / `DISCORD_BOT_TOKEN` / `DISCORD_GUILD_ID` / `DISCORD_BOT_AUTO_START` | Discord bot config. |
| `LOG_LEVEL` | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`. |
| `MAX_UPLOAD_MB` | Upload size limit (default 25). |
| `SESSION_TIMEOUT_MINUTES` | Bot session expiry (default 30). |
| `GEOCODING_USER_AGENT` | Descriptive UA string for Nominatim address search. |
| `ICLOUD_PHOTOS_*` / `PAIRDROP_*` / `APPLE_DEVICES_ENABLED` / `LENSTRACE_SYNC_PATH` | Delivery providers. |

See [.env.example](.env.example) for the full list and
[docs/secrets-and-configuration.md](docs/secrets-and-configuration.md) for how
secrets are stored. Never commit `.env`. Bot tokens, session tokens, and private
paths are kept out of logs (see [SECURITY.md](SECURITY.md)).

## Example workflow (desktop)

1. Drag images in (or use the file picker).
2. Inspect the original metadata.
3. Pick a device (e.g. *Apple iPhone 13 Pro → Main Camera*).
4. Set the capture date/time and time zone (or keep the original).
5. Optionally set a location by address search, map click, or manual lat/long.
6. Review the before/after diff and confirm.
7. Export copies to your chosen folder (optionally with an audit sidecar).

## Testing

```powershell
# Python
pytest
ruff check core backend bots tests scripts
black --check core backend bots tests scripts
mypy core backend bots

# Environment checker
python scripts/check_env.py
python scripts/check_env.py --json
python scripts/check_env.py --strict

# Desktop
cd desktop
npm run typecheck
npm run lint
npm run build
```

## Packaging roadmap (Phase 5, not yet tested)

- Build the backend into a standalone executable with **PyInstaller**.
- Package the Electron app with **electron-builder** (`desktop/electron-builder.yml`).
- Bundle the backend under `resources/backend/` so `BackendManager` can launch it.

See [docs/packaging-windows.md](docs/packaging-windows.md). Packaging scripts are
provided but the produced installer has **not** been verified end-to-end.

## Security

- Bot tokens are **secrets**. Never commit `.env`. If a token is ever exposed,
  regenerate it (via @BotFather or the Discord Developer Portal).
- LensTrace binds its API only to `127.0.0.1` (loopback) with a per-session
  token; delivery routes accept an opaque `export_id`, never raw file paths.
- Transfer integrations never receive Apple Account passwords and never automate
  sign-in.
- Bot logs redact token-shaped strings; the environment checker reports the
  *presence* of secrets, never their contents. Saved tokens are shown only as a
  masked suffix.

See [SECURITY.md](SECURITY.md) and
[docs/secrets-and-configuration.md](docs/secrets-and-configuration.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

[MIT](LICENSE).

## Known limitations

- HEIC/HEIF metadata **writing** is not implemented.
- The map/address search uses OpenStreetMap Nominatim and is rate-limited per
  its usage policy; it is optional and never sends your images.
- The Telegram and Discord bots are scaffolds: their handler logic is
  unit-tested with mocks but they have not been run against the live APIs here.
- The **Send to iPhone** delivery methods are implemented and unit-tested for
  file integrity/verification, but have **not** been verified on a real iPhone,
  iCloud account, or with a real PairDrop transfer. Apple controls final import
  behaviour and any source/provenance labels.
- The PairDrop CLI path is optional and unverified; browser mode is the default.
- Windows packaging is scaffolded but unverified.
- iPhone 16e / iPhone Air / iPhone 17 family presets are marked `placeholder`
  pending confirmation of their exact EXIF `Model` strings.
