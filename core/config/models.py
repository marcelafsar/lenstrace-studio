"""Typed, non-secret configuration models.

These models never hold secret values. Bot tokens are handled by the secrets
service; here we only track whether a bot is *enabled* and its auto-start flag.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class BotKind(str, Enum):
    TELEGRAM = "telegram"
    DISCORD = "discord"


class ConfigSource(str, Enum):
    """Where a configuration/secret value was resolved from."""

    ENVIRONMENT = "environment"
    CREDENTIAL_STORE = "credential-store"
    FILE = "file"
    DOTENV = "dotenv"
    DEFAULT = "default"
    NONE = "none"


class DeliveryConfig(BaseModel):
    """Non-secret configuration for the three delivery providers."""

    icloud_photos_enabled: bool = True
    icloud_photos_path: str | None = None
    pairdrop_enabled: bool = True
    pairdrop_url: str = "https://pairdrop.net/"
    pairdrop_cli_path: str | None = None
    apple_devices_enabled: bool = True
    lenstrace_sync_path: str | None = None


class BotSettings(BaseModel):
    """Non-secret per-bot settings (the token lives in the secrets service)."""

    kind: BotKind
    enabled: bool = False
    auto_start: bool = False
    #: Discord-only optional development guild id (not a secret).
    guild_id: str | None = None


class LifecycleConfig(BaseModel):
    """Bot process-supervision lifecycle options."""

    stop_bots_on_exit: bool = True
    restart_after_crash: bool = False
    max_restarts: int = Field(default=3, ge=0, le=20)


class GeocodingConfig(BaseModel):
    """Address-search (geocoding) configuration. Address search is optional;
    manual coordinates work even when this is disabled."""

    enabled: bool = True
    provider: str = "nominatim"
    user_agent: str = "LensTraceStudio/0.1"
    timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    max_results: int = Field(default=5, ge=1, le=10)
    cache_minutes: int = Field(default=10, ge=0, le=1440)


class LensTraceConfig(BaseModel):
    """Aggregate non-secret application configuration."""

    log_level: str = "INFO"
    max_upload_mb: int = 25
    session_timeout_minutes: int = 30
    geocoding_user_agent: str = "LensTraceStudio/0.1"
    debug: bool = False
    delivery: DeliveryConfig = Field(default_factory=DeliveryConfig)
    geocoding: GeocodingConfig = Field(default_factory=GeocodingConfig)
    telegram: BotSettings = Field(default_factory=lambda: BotSettings(kind=BotKind.TELEGRAM))
    discord: BotSettings = Field(default_factory=lambda: BotSettings(kind=BotKind.DISCORD))
    lifecycle: LifecycleConfig = Field(default_factory=LifecycleConfig)
