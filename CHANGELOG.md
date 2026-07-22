# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
semantic versioning once it reaches 1.0.

## [Unreleased]

### Fixed & added — bot lens metadata, address search, date/time pickers

- **Lens metadata fix**: a selected iPhone lens now always writes a non-empty
  EXIF `LensModel` (previously blank because presets carried empty values and the
  plan only copied non-empty ones). A centralized resolver
  (`core/presets/lens_resolver.py`) uses a verified preset value when present,
  else a transparent generic fallback marked `generic`; optical fields
  (FocalLength/FNumber/FocalLengthIn35mmFilm/LensSpecification) are written only
  when a preset supplies them and are never invented. Switching lenses clears
  stale optical fields; keep/remove-lens honoured.
- **Export verification**: `apply_metadata` reads the exported file back and
  verifies it against the plan; a missing requested `LensModel` is a hard failure
  so bots never send a falsely-successful file. Results carry a SHA-256.
- **Shared geocoding** (`core/location` + `backend/services/geocoding_service.py`)
  with Nominatim, rate limiting, cache, opaque result ids, and safe HTTPS map
  links; optional (manual coordinates always work).
- **Telegram**: address search (results → preview → confirm → search again),
  a month-grid calendar picker, and hour/minute/timezone pickers, keeping manual
  coordinates, Telegram location sharing, and manual date/time.
- **Discord**: address-search modal → results select → confirm, and a
  component year/month/day + time/timezone picker, keeping manual entry;
  owner-only ephemeral controls.
- Env checker + Diagnostics now report geocoding availability; `.env.example`
  gains the `GEOCODING_*` variables.

### Added — Send to iPhone, Bot Control Center, environment checker

- **Unified delivery** (`core/delivery/`, `backend/services/*_service.py`):
  provider-based transfer of exports toward an iPhone via iCloud Photos,
  PairDrop (external, GPL-3.0 — integrated, not vendored), and Apple Devices
  assisted sync. Verified byte-for-byte copy (SHA-256 + metadata), collision
  resolution, URL validation, and a server-side export registry mapping opaque
  `export_id`s to validated paths. Opening a browser/app is never reported as
  delivered.
- **Bot Control Center** (`backend/services/bot_*`, `core/config`, `core/bots`):
  secrets service (env → keyring → file fallback, masked-only status), settings
  service with persisted UI overrides, token validation resolving bot identity
  (rate-limited, never logged), and a process supervisor (separate children, no
  shell, token via env, bounded redacted logs, graceful stop, crash backoff,
  cleanup on exit). Bots disabled by default.
- **Environment checker** (`scripts/check_env.py`, `env_check_service`,
  `/config/status`): shared CLI + API checks with exit codes and no secret
  output.
- **Desktop UI**: section navigation (Editor / Send to iPhone / Bots /
  Diagnostics), delivery hub with offline QR codes, bot setup wizard, and a
  diagnostics panel. Validated `openExternal` bridge in Electron.
- Docs for every new area and an expanded `.env.example`.

### Added — 0.1.0 foundation & desktop MVP

- **Core engine** (`core/`): typed metadata models, validation & path safety,
  GPS decimal↔EXIF conversion, EXIF date/time & UTC-offset utilities, JSON audit
  sidecar, domain exceptions, and a data-driven iPhone preset system
  (iPhone 11–17 families + Generic Apple fallback).
- JPEG/TIFF metadata reading and writing (EXIF-only edit; originals untouched),
  PNG/WebP → JPEG conversion path, and full metadata removal.
- **Local backend** (`backend/`): FastAPI app bound to `127.0.0.1` on an
  ephemeral port, per-session token auth, structured logging with secret
  redaction, and a service layer for files/preview/export.
- **Desktop app** (`desktop/`): Electron + React + Vite + TypeScript guided
  workflow (select → inspect → device → date/time → location → review → export),
  Leaflet map + Nominatim address search, batch export, dark graphite UI.
- **Launcher** (`run_desktop.py`): dependency checks, port/token provisioning,
  backend lifecycle, and clean shutdown.
- **Bot scaffolds** (`bots/`): shared session/temp-file/formatting helpers and
  Telegram + Discord interfaces that import the same engine.
- **Tests**: 70 pytest cases covering gps, datetime, validation, presets, the
  engine, the API, and shared bot logic.
- CI workflows, docs (`architecture`, `metadata-support`, `bot-setup`,
  `packaging-windows`), and packaging scaffolding.

### Known limitations

- HEIC/HEIF metadata writing is not implemented.
- Telegram/Discord bots are not yet run against live APIs.
- Windows packaging (PyInstaller + electron-builder) is scaffolded but untested.
