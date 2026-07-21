# Telegram bot setup

You can configure the Telegram bot either in the desktop **Bots** panel
(recommended) or via environment variables in source mode.

## Get a token

1. Open [@BotFather](https://t.me/BotFather) in Telegram.
2. Send `/newbot` and follow the prompts (name + username).
3. Copy the token BotFather gives you (looks like `123456789:AA...`).

## Configure in the desktop app

1. Open **Bots → Telegram Bot**.
2. Paste the token (use Show to check it), then **Test token** to confirm the
   bot identity (@username).
3. **Save** — the token is stored securely and the input is cleared. It is never
   shown again (only a masked suffix).
4. **Start**. The status shows *Running* and the resolved @username.

Optionally enable *Start automatically when LensTrace opens*.

## Configure via environment (source mode)

In `.env`:

```
TELEGRAM_BOT_ENABLED=true
TELEGRAM_BOT_TOKEN=123456789:your-real-token
TELEGRAM_BOT_AUTO_START=false
```

Then run the bot manually if desired:

```powershell
.\scripts\run_telegram_bot.ps1
# or: python -m bots.telegram_bot.main
```

## Notes

- The bot uses the same `core.MetadataEngine` as the desktop app.
- Send images **as a document** to preserve metadata (the bot warns on
  recompressed photos).
- Commands: `/start`, `/help`, `/privacy`, `/cancel`.
- The token is never logged. Telegram's API requires the token in the request
  path; LensTrace never logs that URL.
- **Not verified against the live Telegram API in this repository.**
