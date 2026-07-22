# Architecture

LensTrace Studio is organised around a single shared metadata engine consumed by
three interfaces. No interface duplicates metadata logic.

```
                         ┌─────────────────────────────┐
                         │        core (engine)        │
                         │  models · validation · gps  │
                         │  datetime · presets · audit │
                         │  reader · writer · engine   │
                         └──────────────┬──────────────┘
                                        │ imported by
        ┌───────────────────────────────┼───────────────────────────────┐
        │                               │                               │
┌───────▼────────┐              ┌───────▼────────┐              ┌────────▼───────┐
│    backend     │              │  telegram_bot  │              │   discord_bot  │
│  FastAPI @     │              │ python-telegram│              │   discord.py   │
│  127.0.0.1     │              │     -bot       │              │                │
└───────┬────────┘              └────────────────┘              └────────────────┘
        │ HTTP + session token
┌───────▼────────┐
│  desktop app   │  Electron + React + Vite + TypeScript
└────────────────┘
```

## Layers

### `core/`
Pure Python, no web or bot dependencies. The public surface is
`MetadataEngine` with `inspect_image`, `build_change_plan`,
`validate_change_plan`, `build_diff`, `apply_metadata`, `remove_metadata`, and
`export_image`. Data flows as typed Pydantic models (`ChangePlan`,
`MetadataSummary`, `ChangeDiff`, `ExportResult`).

The engine never mutates the source file. For JPEG/TIFF it copies the file, then
edits only the EXIF segment (no pixel recompression). For PNG/WebP it can convert
to JPEG (recompresses, with a warning). HEIC/HEIF writing is not implemented.

### `backend/`
A local FastAPI application used **only** by the desktop app:

- Binds to `127.0.0.1` on an ephemeral port chosen by the launcher.
- Requires a per-session token (`X-LensTrace-Token`) on every route except
  `/health`.
- Thin routers delegate to a service layer (`file_service`, `preview_service`,
  `session_service`).

### `desktop/`
Electron main process (`electron/main.ts`) owns native dialogs and, in a packaged
build, the backend lifecycle (`backendManager.ts`). The preload exposes a small,
explicit bridge. The React renderer is a guided 7-step workflow with a central
API client (`src/services/api.ts`) and a Zustand store.

### `bots/`
`bots/shared` is library-agnostic (sessions, temp workspaces, formatting) so it
is unit-testable. `telegram_bot` and `discord_bot` import their libraries only
when run and call the same engine.

## Request/response flow (desktop export)

1. Renderer uploads bytes → `POST /files/upload` → stored in a per-run work dir,
   registered in the session store, returns a `file_id` + thumbnail.
2. Renderer collects device/date/location choices in the store.
3. `POST /metadata/preview` builds a `ChangePlan` and returns a before/after diff
   plus the destination filename — nothing is written yet.
4. On confirm, `POST /metadata/export` applies the plan, writes the new copy and
   optional audit sidecar, and returns the result.

## Security boundaries

See [SECURITY.md](../SECURITY.md). Key points: loopback-only backend, session
token, filename/path sanitisation, no external image upload, secret redaction in
logs.
