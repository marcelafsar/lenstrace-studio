# Contributing to LensTrace Studio

Thanks for your interest! This project values clean architecture and honest
status reporting — features are only described as "working" once they are
actually tested.

## Ground rules

- Keep the layers separated: metadata logic lives in `core/` only. Never write
  or read EXIF directly from a FastAPI route or a bot handler — call
  `core.MetadataEngine`.
- Keep modules focused (roughly < 300 lines where practical).
- Do not commit personal photos, real coordinates, secrets, or `.env` files.
- Do not invent Apple lens/EXIF values. Mark uncertain preset data with
  `source_status: "placeholder"`.

## Development environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
cd desktop; npm install; cd ..
```

## Before opening a PR

Run the full local check suite:

```powershell
pytest
ruff check core backend bots tests
black --check core backend bots tests
mypy core backend

cd desktop
npm run typecheck
npm run lint
npm run build
cd ..
```

- Add or update tests for any behaviour you change.
- Bot changes should be covered by mock-based tests in `tests/test_bots.py`
  (do not require a live Discord/Telegram connection).
- Update the relevant docs and `CHANGELOG.md`.

## Commit style

Small, focused commits with clear messages. Reference issues where relevant.

## Reporting security issues

See [SECURITY.md](SECURITY.md) — please do not open a public issue for
vulnerabilities.
