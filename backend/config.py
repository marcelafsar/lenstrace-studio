"""Backend configuration, loaded from environment variables.

The launcher (``run_desktop.py``) sets ``LENSTRACE_HOST``, ``LENSTRACE_PORT``,
and ``LENSTRACE_SESSION_TOKEN`` before starting the server. Defaults are safe
for local development.
"""

from __future__ import annotations

import secrets
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BackendSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LENSTRACE_", env_file=".env", extra="ignore")

    # Networking — bound to loopback only, never 0.0.0.0.
    host: str = "127.0.0.1"
    port: int = 0  # 0 => let the OS/launcher pick an ephemeral port

    # Auth — a random token supplied by the launcher. If unset, one is
    # generated so the server is never unauthenticated, even in dev.
    session_token: str = Field(default_factory=lambda: secrets.token_urlsafe(32))

    # Limits
    max_upload_mb: int = 25

    # Storage — per-run working directory for uploads/exports.
    work_dir: Path = Path.home() / ".lenstrace" / "work"
    default_output_dir: Path = Path.home() / "Pictures" / "LensTrace Output"

    log_level: str = "INFO"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


_settings: BackendSettings | None = None


def get_settings() -> BackendSettings:
    """Return the process-wide settings singleton."""
    global _settings
    if _settings is None:
        _settings = BackendSettings()
        _settings.work_dir.mkdir(parents=True, exist_ok=True)
    return _settings
