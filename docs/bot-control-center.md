# Bot Control Center

The desktop **Bots** panel configures and supervises the Telegram and Discord
bots without editing files. It is designed for users who do not want to touch
environment variables.

## Per-bot status

Each bot shows one of: not configured, configuration incomplete, ready,
starting, running, stopping, stopped, authentication failed, connection failed,
crashed, disabled — plus last-started time, uptime, last (redacted) error,
restart count, whether a token is configured, and the resolved bot identity
after successful validation.

## Controls (implemented)

- Enable/paste token with show/hide; **Test token** resolves the bot identity;
  **Save** stores it securely and immediately clears the input field.
- Start / Stop / Restart (Start is disabled until a token is configured).
- "Start automatically when LensTrace opens" toggle (off by default).
- View recent (redacted) logs.
- Clear saved token (with confirmation; stops the bot first).
- Copy a beginner setup checklist; open the official setup page.

The saved token is **never** shown again — only a masked suffix (e.g. `…AB12`)
and its storage source.

## Setup wizards

- **Telegram:** explains getting a token from @BotFather, validates it, shows the
  resolved identity, saves, and starts. See
  [telegram-bot-setup.md](telegram-bot-setup.md).
- **Discord:** explains creating an application/bot and required
  `applications.commands` scope, optional dev guild id, validation, and start.
  See [discord-bot-setup.md](discord-bot-setup.md).

Wizards never request account passwords and never automate account login.

## Safety

- Only the authenticated local desktop API can control bots.
- Bots run as separate child processes supervised by the backend — see
  [bot-process-supervision.md](bot-process-supervision.md).
- Tokens are handled by the secrets service — see
  [secrets-and-configuration.md](secrets-and-configuration.md).

## Status

Backend and UI are implemented and unit-tested with mocked processes/validators.
The bots have **not** been run against the live Telegram/Discord APIs in this
repository; validate end-to-end with a real token before relying on them.
