# Bot setup

Both bots import the same `core.MetadataEngine` as the desktop app. They are
**scaffolds**: handler logic is unit-tested with mocks (`tests/test_bots.py`) but
they have not been run against the live Telegram/Discord APIs in this repo.
Verify the current official library docs before extending them.

## Prerequisites

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt   # installs both bot libs
Copy-Item .env.example .env
```

Set the relevant token in `.env`. Never commit `.env`.

## Telegram

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. Put it in `.env` as `TELEGRAM_BOT_TOKEN=...`.
3. Run:

   ```powershell
   .\scripts\run_telegram_bot.ps1
   # or: python -m bots.telegram_bot.main
   ```

Commands: `/start`, `/help`, `/privacy`, `/cancel`. Send an image **as a
document** (not a compressed photo) to preserve metadata; the bot warns if it
receives a recompressed photo.

## Discord

1. Create an application + bot at the
   [Discord Developer Portal](https://discord.com/developers/applications).
2. Copy the bot token into `.env` as `DISCORD_BOT_TOKEN=...`.
3. Invite the bot with the `applications.commands` scope.
4. Run:

   ```powershell
   .\scripts\run_discord_bot.ps1
   # or: python -m bots.discord_bot.main
   ```

Slash commands: `/metadata inspect`, `/metadata edit`, `/metadata remove`,
`/metadata help`. Configuration replies are ephemeral; sessions are per-user and
expire after `SESSION_TIMEOUT_MINUTES`.

## Privacy behaviour

- Uploaded files go into isolated temporary workspaces and are deleted right
  after the reply is sent.
- Image contents and coordinates are not logged at normal log levels.
- A configurable upload size limit (`MAX_UPLOAD_MB`) is enforced.
- Users are never required to share a location.
