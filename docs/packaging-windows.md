# Windows packaging (Phase 5 — scaffolded, not yet verified)

> ⚠️ The steps below describe the intended packaging pipeline. The produced
> installer has **not** been built and tested end-to-end in this repository. Do
> not treat packaging as a finished feature.

The target is a single Windows distributable that bundles:

1. The Python backend compiled to a standalone executable with **PyInstaller**.
2. The Electron app packaged with **electron-builder**.

## 1. Build the backend executable

```powershell
.\scripts\build_backend.ps1
```

This runs PyInstaller against `backend/main.py` to produce
`backend_dist/lenstrace-backend.exe`. The executable reads `LENSTRACE_HOST`,
`LENSTRACE_PORT`, and `LENSTRACE_SESSION_TOKEN` from the environment, exactly as
in development.

Open items to validate:

- Ensure `tzdata`, Pillow, and piexif data files are collected.
- Confirm the bundled `core/presets/iphone_presets.json` is included.

## 2. Wire the backend into Electron

In production the Electron main process uses `electron/backendManager.ts` to:

- pick a free loopback port,
- generate a session token,
- spawn `resources/backend/lenstrace-backend.exe`, and
- wait for `/health` before creating the window.

Uncomment the `extraResources` block in `desktop/electron-builder.yml` so the
built executable is copied to `resources/backend/`.

## 3. Build the installer

```powershell
.\scripts\build_desktop.ps1
```

This runs `npm run build` then `electron-builder`, producing an NSIS installer
under `desktop/release/`.

## 4. Test

- Install on a clean Windows machine (no Python/Node).
- Confirm the backend starts on an ephemeral loopback port with a fresh token.
- Confirm inspect / edit / export all work offline.
- Confirm no window binds to a public interface.

Only after these pass should a release workflow be added.
