# Discord bot — manual testing

A safe checklist for verifying the Discord bot end to end. Configure the token in
the desktop **Bots** panel (or `.env`); it is never printed. For fast command
appearance during testing, set a **development guild ID** (instant per-guild
sync); without it, global commands can take up to an hour to appear.

## Checklist

1. Start the Discord bot through LensTrace (Bots → Discord → Start).
2. Wait until the panel shows **Authenticated**, **Gateway ready**, and
   **Commands synced (N)**. Until commands are synced it is not shown as a green
   "Running" ready state.
3. In your server, type `/metadata` — confirm `inspect`, `edit`, `remove`, and
   `help` appear.
4. Run `/metadata inspect` with a PNG attachment — the reply is ephemeral and
   shows the metadata. Confirm the interaction does **not** time out (it defers
   first, then follows up).
5. Run `/metadata remove` with a PNG — receive the cleaned file as an attachment.
6. Run `/metadata edit` with a PNG — an ephemeral control panel appears (device
   select, date/time, location, Review, Cancel).
7. Configure a device via the select menus and a date via the modal, press
   **Review**, then **Confirm & export** — receive the processed attachment.
8. Ask another user to click your ephemeral controls (or simulate) — confirm they
   are rejected ("This isn't your editing session").
9. Leave an edit panel idle past its timeout — confirm controls expire and temp
   files are cleaned.
10. Use the **Resync commands** button in the Bots panel — confirm commands
    re-sync (the bot restarts and reports *Commands synced* again).
11. Run a command that triggers an error (e.g. a corrupt attachment) — confirm a
    visible ephemeral error rather than a silent timeout.
12. Confirm the Bot Control Center reports **actual** readiness (not green until
    gateway-ready and commands-synced), and that no token appears in any log.

## Notes

- Slash-command-only workflows do **not** require the message-content intent.
- Commands sync once per process start (not on every reconnect); use **Resync
  commands** to force a fresh sync.
