"""Telegram bot entry point.

Run with:  python -m bots.telegram_bot.main
Requires the TELEGRAM_BOT_TOKEN environment variable.

Emits structured BOT_STATUS/BOT_ERROR lines so the LensTrace Bot Control Center
can report real readiness (authenticated / polling ready), not just "the process
exists".
"""

from __future__ import annotations

import logging
import os
import sys

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from backend.logging_config import configure_logging
from bots.shared.status_events import emit_error, emit_status, force_unbuffered_stdout
from bots.shared.temporary_files import cleanup_stale_workspaces
from bots.telegram_bot import handlers

_KIND = "telegram"


def build_application() -> Application:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set. Copy .env.example to .env.", file=sys.stderr)
        raise SystemExit(1)

    app = ApplicationBuilder().token(token).post_init(_post_init).build()

    # Commands work whether or not the user is mid-conversation.
    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("help", handlers.cmd_help))
    app.add_handler(CommandHandler("privacy", handlers.cmd_privacy))
    app.add_handler(CommandHandler("cancel", handlers.cmd_cancel))

    # KEY FIX: match EVERY document, then decide acceptance inside the handler.
    # `filters.Document.IMAGE` only matches image/* MIME types and silently drops
    # iOS/desktop image documents sent as application/octet-stream.
    app.add_handler(MessageHandler(filters.Document.ALL, handlers.on_document))
    app.add_handler(MessageHandler(filters.PHOTO, handlers.on_photo))
    app.add_handler(MessageHandler(filters.LOCATION, handlers.on_location))
    app.add_handler(CallbackQueryHandler(handlers.on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.on_text))

    # Global error handler so no failure is silent.
    app.add_error_handler(handlers.on_error)
    return app


async def _post_init(app: Application) -> None:
    """Confirm authentication and announce readiness once the bot is initialised."""
    try:
        me = await app.bot.get_me()
        emit_status(_KIND, "authenticated", username=me.username or "unknown")
        # run_polling starts immediately after post_init returns.
        emit_status(_KIND, "polling_ready", username=me.username or "unknown")
        logging.getLogger(__name__).info("Telegram bot authenticated as @%s", me.username)
    except Exception as exc:  # noqa: BLE001
        emit_error(_KIND, "startup", type(exc).__name__)
        raise


def main() -> None:
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    force_unbuffered_stdout()
    removed = cleanup_stale_workspaces()
    if removed:
        logging.getLogger(__name__).info("Cleaned %d stale bot workspace(s).", removed)
    logging.getLogger(__name__).info("Starting Telegram bot (polling).")
    app = build_application()
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
