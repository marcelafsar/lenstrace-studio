"""Chat-bot interfaces for LensTrace Studio.

Both the Telegram and Discord bots import the SAME :class:`core.MetadataEngine`
used by the desktop app. No metadata-writing logic lives in bot handlers.

The ``bots.shared`` subpackage is pure Python (no bot libraries) so it can be
unit-tested without a network connection. The ``telegram_bot`` and
``discord_bot`` subpackages import their respective libraries only when run.
"""
