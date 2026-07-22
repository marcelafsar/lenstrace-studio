# Secrets and configuration

LensTrace separates **non-secret settings** from **secret values** (bot tokens).

## Non-secret settings

Loaded by `backend/services/settings_service.py` into a typed
`core.config.models.LensTraceConfig`. Priority per value:

1. explicit process environment variable
2. source-mode `.env`
3. built-in default

UI toggles that the Bots panel can change (enabled / auto-start / guild id) are
persisted as an overlay (`~/.lenstrace/settings.json`, overridable via
`LENSTRACE_STATE_DIR`) and take precedence over `.env` defaults for those keys.
Booleans are parsed strictly (`true/false`, `1/0`, `yes/no`, `on/off`).

## Secret values (bot tokens)

Handled only by `backend/services/secrets_service.py`. Resolution priority:

1. process environment variable
2. OS credential store via `keyring` (when available)
3. local file fallback (`~/.lenstrace/secrets.json`, overridable via
   `LENSTRACE_SECRETS_DIR`) — used only if keyring is unavailable, and reported
   honestly as the `file` source
4. source-mode `.env`

Writing prefers the OS credential store and falls back to the file store.

### What the renderer/API can see

Only: `configured` (true/false), the source
(`environment`/`credential-store`/`file`/`dotenv`/`none`), and a **masked
suffix** (e.g. `…AB12`). The full secret is **never** returned by any GET route,
never logged, never placed in exceptions, and never written to frontend state,
audit files, or crash reports. Placeholder values (e.g. `your-token-here`) are
treated as unconfigured.

## Safe token handling (enforced)

- Tokens are passed to bot child processes via the **environment**, never argv.
- Token validation puts the value in an HTTP header (Discord) or the API path
  required by the provider (Telegram) — never logged.
- The session token uses constant-time comparison; `.env` stays git-ignored.
- The token input field is cleared immediately after a successful save.

If secure OS storage is unavailable, the app uses the file fallback and reports
the `file` source so you know the token is stored in your home directory rather
than the OS credential vault.
