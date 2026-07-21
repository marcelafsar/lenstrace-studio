# PairDrop integration

[PairDrop](https://github.com/schlagmichdoch/PairDrop) is an independent,
open-source (GPL-3.0) browser/PWA WebRTC file-transfer project by
schlagmichdoch. LensTrace integrates with it as an **external service**.

## Licensing boundary

Because PairDrop is GPL-3.0 and LensTrace is MIT-licensed, LensTrace treats
PairDrop strictly as an external integration:

- LensTrace does **not** copy, vendor, bundle, modify, or redistribute any
  PairDrop source or frontend bundle.
- PairDrop is **not** a component of LensTrace.
- LensTrace only opens a PairDrop URL in the user's browser and shows
  instructions. The integration adapter (`backend/services/pairdrop_service.py`)
  is LensTrace's own MIT code.

Attribution: PairDrop © schlagmichdoch and contributors, GPL-3.0. See the
PairDrop repository for its license and documentation. Verify current PairDrop
behaviour and CLI syntax against its official docs before extending this
adapter.

## Browser fallback (default, implemented)

1. LensTrace shows the export summary and the PairDrop host.
2. It renders a QR code whose payload is **only** the validated PairDrop URL —
   never file bytes, Windows paths, tokens, image metadata, or coordinates.
3. Buttons: Open PairDrop (validated `openExternal`), Open output folder, and
   copy actions.
4. You open the same PairDrop instance on the iPhone, pick the device, choose
   the LensTrace-exported file, accept on the iPhone, and use iOS share/save.

Opening the browser is **not** treated as completed delivery.

## URL validation (implemented)

The default instance is `https://pairdrop.net/`. A custom instance is allowed,
but every URL is validated: HTTPS required (except `localhost` for development),
and `javascript:`, `data:`, `file:`, other schemes, and embedded credentials are
rejected. The hostname is shown before opening.

## Optional CLI mode

`PAIRDROP_CLI_PATH` (or a `pairdrop` executable on PATH) is detected and
reported. When invoked, arguments are built as an explicit list (never
`shell=True`), handling spaces/Unicode. The CLI is optional; browser mode is the
default and Git Bash is not required. **CLI transfer is not exercised** in this
repository — treat it as scaffolding pending verification against the current
official CLI.

## Privacy note

PairDrop normally uses browser-based peer-to-peer transfer; a relay may be
involved depending on your network. LensTrace does not control PairDrop's
servers. **PairDrop transfers the exported file; LensTrace cannot control Apple
Photos source or provenance labels.**
