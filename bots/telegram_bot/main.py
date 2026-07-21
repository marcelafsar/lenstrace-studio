"""Telegram bot entry point.

Run with:  python -m bots.telegram_bot.main
Requires the TELEGRAM_BOT_TOKEN environment variable.

NOTE: This bot has not been run against the live Telegram API in this repo's
CI. Handler logic is unit-tested with mocks; verify end-to-end before relying
on it in production.
"""

from __future__ import annotations

import logging
import os
import sys

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from backend.logging_config import configure_logging
from bots.telegram_bot import handlers


def build_application():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set. Copy .env.example to .env.", file=sys.stderr)
        raise SystemExit(1)

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("help", handlers.cmd_help))
    app.add_handler(CommandHandler("privacy", handlers.cmd_privacy))
    app.add_handler(CommandHandler("cancel", handlers.cmd_cancel))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handlers.on_document))
    app.add_handler(MessageHandler(filters.PHOTO, handlers.on_photo))
    app.add_handler(CallbackQueryHandler(handlers.on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.on_text))
    return app


def main() -> None:
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    logging.getLogger(__name__).info("Starting Telegram bot (polling).")
    app = build_application()
    app.run_polling(allowed_updates=None)


if __name__ == "__main__":
    main()
