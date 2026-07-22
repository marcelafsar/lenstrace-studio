"""Bot configuration + token validation, combining settings and secrets.

Token validation resolves the bot's public identity via the official APIs:
  * Telegram: ``getMe`` (python-telegram-bot if available, else a direct call).
  * Discord: ``GET /users/@me`` with a Bot authorization header.

The token is never logged, never returned to the renderer, and never placed in
an exception message. Manual validation is rate-limited.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from threading import Lock

from pydantic import BaseModel

from backend.logging_config import get_logger
from backend.services import secrets_service, settings_service
from core.config.models import BotKind, BotSettings, ConfigSource

logger = get_logger(__name__)

TOKEN_KEYS: dict[BotKind, str] = {
    BotKind.TELEGRAM: "TELEGRAM_BOT_TOKEN",
    BotKind.DISCORD: "DISCORD_BOT_TOKEN",
}

_MIN_VALIDATION_INTERVAL_S = 3.0
_last_validation: dict[BotKind, float] = {}
_rate_lock = Lock()


class BotIdentity(BaseModel):
    username: str | None = None
    display_name: str | None = None
    bot_id: str | None = None


class BotValidation(BaseModel):
    valid: bool
    identity: BotIdentity | None = None
    error: str | None = None


class BotConfigStatus(BaseModel):
    """Non-secret combined status for a bot (safe for the API)."""

    kind: BotKind
    enabled: bool
    auto_start: bool
    guild_id: str | None = None
    token_configured: bool
    token_source: ConfigSource
    token_masked_suffix: str | None = None
    identity: BotIdentity | None = None


def _settings_for(kind: BotKind) -> BotSettings:
    config = settings_service.get_config()
    return config.telegram if kind == BotKind.TELEGRAM else config.discord


def token_key(kind: BotKind) -> str:
    return TOKEN_KEYS[kind]


def resolve_token(kind: BotKind) -> tuple[str | None, ConfigSource]:
    """Resolve a bot's token value + source (never expose this via the API)."""
    return secrets_service.resolve_secret(token_key(kind))


def get_status(kind: BotKind, identity: BotIdentity | None = None) -> BotConfigStatus:
    """Return the non-secret combined status for a bot."""
    settings = _settings_for(kind)
    secret = secrets_service.secret_status(token_key(kind))
    return BotConfigStatus(
        kind=kind,
        enabled=settings.enabled,
        auto_start=settings.auto_start,
        guild_id=settings.guild_id,
        token_configured=secret.configured,
        token_source=secret.source,
        token_masked_suffix=secret.masked_suffix,
        identity=identity,
    )


def save_token(kind: BotKind, token: str) -> ConfigSource:
    """Persist a bot token via the secrets service. Returns the storage source."""
    if not token or not token.strip():
        from core.exceptions import LensTraceError

        raise LensTraceError("Empty token", user_message="Please paste a bot token.")
    source = secrets_service.store_secret(token_key(kind), token)
    logger.info("Saved %s bot token to %s (value hidden).", kind.value, source.value)
    return source


def clear_token(kind: BotKind) -> bool:
    removed = secrets_service.delete_secret(token_key(kind))
    logger.info("Cleared %s bot token (removed=%s).", kind.value, removed)
    return removed


# ---- Validation ----------------------------------------------------------


def _rate_limited(kind: BotKind) -> bool:
    with _rate_lock:
        now = time.monotonic()
        last = _last_validation.get(kind, 0.0)
        if now - last < _MIN_VALIDATION_INTERVAL_S:
            return True
        _last_validation[kind] = now
        return False


def validate_token(
    kind: BotKind,
    *,
    token: str | None = None,
    validator: Callable[[BotKind, str], BotValidation] | None = None,
) -> BotValidation:
    """Validate a bot token and resolve its identity.

    If ``token`` is None, the stored token is used. ``validator`` can be
    injected in tests to avoid real network calls.
    """
    if _rate_limited(kind):
        return BotValidation(valid=False, error="Please wait a moment before testing again.")

    value = token if token is not None else resolve_token(kind)[0]
    if not value:
        return BotValidation(valid=False, error="No token configured.")

    fn = validator or _default_validator
    try:
        return fn(kind, value)
    except Exception as exc:  # noqa: BLE001 - never leak token in error text
        logger.warning("Token validation error for %s bot (details hidden).", kind.value)
        return BotValidation(valid=False, error=f"Validation failed: {type(exc).__name__}")


def _default_validator(kind: BotKind, token: str) -> BotValidation:
    if kind == BotKind.TELEGRAM:
        return _validate_telegram(token)
    return _validate_discord(token)


def _validate_telegram(token: str) -> BotValidation:
    import httpx

    # Telegram's API requires the token in the path; the URL is never logged.
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        resp = httpx.get(url, timeout=10.0)
    except httpx.HTTPError:
        return BotValidation(valid=False, error="Could not reach Telegram.")
    if resp.status_code == 401:
        return BotValidation(valid=False, error="Telegram rejected the token.")
    if resp.status_code != 200:
        return BotValidation(valid=False, error=f"Telegram returned {resp.status_code}.")
    data = resp.json().get("result", {})
    return BotValidation(
        valid=True,
        identity=BotIdentity(
            username=data.get("username"),
            display_name=data.get("first_name"),
            bot_id=str(data.get("id")) if data.get("id") is not None else None,
        ),
    )


def _validate_discord(token: str) -> BotValidation:
    import httpx

    # Token goes in the Authorization header, never the URL.
    headers = {"Authorization": f"Bot {token}"}
    try:
        resp = httpx.get("https://discord.com/api/v10/users/@me", headers=headers, timeout=10.0)
    except httpx.HTTPError:
        return BotValidation(valid=False, error="Could not reach Discord.")
    if resp.status_code == 401:
        return BotValidation(valid=False, error="Discord rejected the token.")
    if resp.status_code != 200:
        return BotValidation(valid=False, error=f"Discord returned {resp.status_code}.")
    data = resp.json()
    username = data.get("username")
    return BotValidation(
        valid=True,
        identity=BotIdentity(
            username=username,
            display_name=username,
            bot_id=str(data.get("id")) if data.get("id") is not None else None,
        ),
    )
