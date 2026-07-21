# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
semantic versioning once it reaches 1.0.

## [Unreleased]

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
