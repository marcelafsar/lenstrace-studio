"""Load non-secret application configuration from the environment and .env.

Priority for each value: explicit process environment variable, then a value
from the source-mode ``.env`` file, then a built-in default. Secret values
(bot tokens) are intentionally NOT read here — see :mod:`secrets_service`.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.config.models import (
    BotKind,
    BotSettings,
    DeliveryConfig,
    LensTraceConfig,
    LifecycleConfig,
)
from core.config.validation import parse_bool, parse_optional_int

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _REPO_ROOT / ".env"


def _state_dir() -> Path:
    """Directory for persisted UI settings overrides (overridable in tests)."""
    override = os.environ.get("LENSTRACE_STATE_DIR")
    return Path(override) if override else Path.home() / ".lenstrace"


def _overrides_file() -> Path:
    return _state_dir() / "settings.json"


def _read_overrides() -> dict[str, Any]:
    path = _overrides_file()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_overrides(data: dict[str, Any]) -> None:
    path = _overrides_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def set_bot_setting(kind: BotKind, field: str, value: Any) -> None:
    """Persist a UI-controlled bot setting (enabled/auto_start/guild_id)."""
    if field not in {"enabled", "auto_start", "guild_id"}:
        raise ValueError(f"Unsupported bot setting: {field}")
    data = _read_overrides()
    data[f"{kind.value}.{field}"] = value
    _write_overrides(data)
    reload_config()


def _merged_env() -> dict[str, str]:
    """Return .env values overlaid by real process env (process env wins)."""
    merged: dict[str, str] = {}
    if _ENV_FILE.exists():
        try:
            from dotenv import dotenv_values

            merged.update({k: v for k, v in dotenv_values(_ENV_FILE).items() if v is not None})
        except Exception:  # noqa: BLE001 - dotenv optional/robustness
            pass
    merged.update(dict(os.environ))
    return merged


def load_config(env: dict[str, str] | None = None) -> LensTraceConfig:
    """Build a :class:`LensTraceConfig` from the merged environment."""
    e = env if env is not None else _merged_env()

    def get(key: str, default: str = "") -> str:
        return e.get(key, default)

    delivery = DeliveryConfig(
        icloud_photos_enabled=parse_bool(e.get("ICLOUD_PHOTOS_ENABLED"), default=True),
        icloud_photos_path=e.get("ICLOUD_PHOTOS_PATH") or None,
        pairdrop_enabled=parse_bool(e.get("PAIRDROP_ENABLED"), default=True),
        pairdrop_url=get("PAIRDROP_URL", "https://pairdrop.net/") or "https://pairdrop.net/",
        pairdrop_cli_path=e.get("PAIRDROP_CLI_PATH") or None,
        apple_devices_enabled=parse_bool(e.get("APPLE_DEVICES_ENABLED"), default=True),
        lenstrace_sync_path=e.get("LENSTRACE_SYNC_PATH") or None,
    )

    # UI-controlled overrides (persisted via set_bot_setting) take precedence
    # over .env defaults for these specific toggles.
    ov = _read_overrides()

    def ov_bool(key: str, env_default: bool) -> bool:
        return bool(ov[key]) if key in ov else env_default

    def ov_str(key: str, env_default: str | None) -> str | None:
        return (str(ov[key]) or None) if key in ov else env_default

    telegram = BotSettings(
        kind=BotKind.TELEGRAM,
        enabled=ov_bool(
            "telegram.enabled", parse_bool(e.get("TELEGRAM_BOT_ENABLED"), default=False)
        ),
        auto_start=ov_bool(
            "telegram.auto_start", parse_bool(e.get("TELEGRAM_BOT_AUTO_START"), default=False)
        ),
    )
    discord = BotSettings(
        kind=BotKind.DISCORD,
        enabled=ov_bool("discord.enabled", parse_bool(e.get("DISCORD_BOT_ENABLED"), default=False)),
        auto_start=ov_bool(
            "discord.auto_start", parse_bool(e.get("DISCORD_BOT_AUTO_START"), default=False)
        ),
        guild_id=ov_str("discord.guild_id", e.get("DISCORD_GUILD_ID") or None),
    )

    lifecycle = LifecycleConfig(
        stop_bots_on_exit=parse_bool(e.get("LENSTRACE_STOP_BOTS_ON_EXIT"), default=True),
        restart_after_crash=parse_bool(e.get("LENSTRACE_RESTART_AFTER_CRASH"), default=False),
        max_restarts=parse_optional_int(e.get("LENSTRACE_MAX_RESTARTS")) or 3,
    )

    return LensTraceConfig(
        log_level=get("LOG_LEVEL", "INFO") or "INFO",
        max_upload_mb=parse_optional_int(e.get("MAX_UPLOAD_MB")) or 25,
        session_timeout_minutes=parse_optional_int(e.get("SESSION_TIMEOUT_MINUTES")) or 30,
        geocoding_user_agent=get("GEOCODING_USER_AGENT", "LensTraceStudio/0.1")
        or "LensTraceStudio/0.1",
        debug=parse_bool(e.get("LENSTRACE_DEBUG"), default=False),
        delivery=delivery,
        telegram=telegram,
        discord=discord,
        lifecycle=lifecycle,
    )


@lru_cache(maxsize=1)
def get_config() -> LensTraceConfig:
    """Process-wide cached configuration."""
    return load_config()


def reload_config() -> LensTraceConfig:
    """Clear the cache and reload (used after settings change)."""
    get_config.cache_clear()
    return get_config()
