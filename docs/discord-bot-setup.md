# Discord bot setup

Configure the Discord bot in the desktop **Bots** panel (recommended) or via
environment variables in source mode.

## Create an application and bot

1. Open the [Discord Developer Portal](https://discord.com/developers/applications).
2. **New Application** → **Bot** → **Reset Token** and copy the bot token.
3. Under **Installation / OAuth2**, use the `applications.commands` scope (and
   `bot` if you need a classic invite). Slash commands do **not** require
   privileged intents.
4. Invite the bot to your server with that scope.

## Configure in the desktop app

1. Open **Bots → Discord Bot**.
2. Paste the token; optionally set a **development guild ID** (for instant
   command sync during testing).
3. **Test token** to confirm the bot identity, then **Save** (input clears; token
   is never shown again).
4. **Start**. The bot logs in and syncs its `/metadata` commands.

## Configure via environment (source mode)

```
DISCORD_BOT_ENABLED=true
DISCORD_BOT_TOKEN=your-real-bot-token
DISCORD_GUILD_ID=            # optional numeric guild id
DISCORD_BOT_AUTO_START=false
```

```powershell
.\scripts\run_discord_bot.ps1
# or: python -m bots.discord_bot.main
```

## Notes

- Commands: `/metadata inspect|edit|remove|help`, using the shared engine.
- The token is sent only in the `Authorization: Bot …` header (never a URL) and
  is never logged.
- Prefer slash commands/interactions; avoid privileged intents unless genuinely
  required.
- **Not verified against the live Discord API in this repository.**
