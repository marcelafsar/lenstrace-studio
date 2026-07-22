# Environment checker

One shared checking service powers both a CLI and an authenticated API endpoint,
so the desktop **Diagnostics** panel and the terminal report the same results.
No secret value is ever printed.

## CLI

```powershell
python scripts/check_env.py
python scripts/check_env.py --service all|telegram|discord|delivery
python scripts/check_env.py --json
python scripts/check_env.py --strict
python scripts/check_env.py --connectivity
python scripts/check_env.py --no-color
```

Output uses `[PASS]`, `[WARN]`, `[FAIL]` lines and a summary. Exit codes:

| Code | Meaning |
|------|---------|
| 0 | all required checks passed |
| 1 | a required check failed |
| 2 | configuration is invalid |
| 3 | unexpected checker error |

- **Non-strict** (default): missing optional bot tokens are warnings.
- **Strict**: an *enabled* integration with missing configuration fails.
- **JSON** (`--json`): machine-readable, no ANSI codes.
- **Connectivity** (`--connectivity`): also validates bot tokens over the network
  (rate-limited); off by default so checks stay offline/fast.

## Checks

- **Core desktop:** Python version, Node/npm, importable Python deps, desktop
  package + node_modules, loopback bind, required folders.
- **General:** `.env` presence, `.env` is git-ignored, `.env.example` present,
  upload limit, session timeout, geocoding user agent.
- **Telegram / Discord:** token configured, not a placeholder, guild id valid,
  optional identity resolution.
- **Delivery:** iCloud detected/manual, PairDrop URL valid, PairDrop CLI status,
  Apple Devices detected/manual, LensTrace Sync folder writable.

## API / UI

`GET /config/status` (and `POST /config/recheck`) return the same report without
secrets, behind the session token. The Diagnostics panel groups results by
category, shows counts, offers a network-connectivity toggle, and can copy a
redacted report.
