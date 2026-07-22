"""Secret (bot token) storage abstraction.

Resolution priority when reading:
  1. explicit process environment variable
  2. OS credential store (``keyring``) when available
  3. local encrypted-at-rest? — no: a plaintext file fallback under the user's
     home config dir, used only when keyring is unavailable (reported honestly)
  4. source-mode ``.env``

Writing prefers the OS credential store; if unavailable it falls back to the
local file store and reports that source honestly.

The full secret value is NEVER returned to the renderer. Callers that build API
responses must use :func:`secret_status`, which exposes only a masked suffix.
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from threading import Lock

from pydantic import BaseModel

from core.config.models import ConfigSource
from core.config.validation import looks_like_placeholder

_KEYRING_SERVICE = "LensTraceStudio"
_lock = Lock()


def _secrets_dir() -> Path:
    """Directory for the file-store fallback.

    Overridable via ``LENSTRACE_SECRETS_DIR`` (used by tests so they never touch
    the real user home directory).
    """
    override = os.environ.get("LENSTRACE_SECRETS_DIR")
    return Path(override) if override else Path.home() / ".lenstrace"


def _secrets_file() -> Path:
    return _secrets_dir() / "secrets.json"


try:  # keyring is optional; packaging may or may not include it.
    import keyring

    _KEYRING_AVAILABLE = True
except Exception:  # noqa: BLE001
    _KEYRING_AVAILABLE = False


class SecretStatus(BaseModel):
    """Non-sensitive description of a stored secret (safe for the API)."""

    key: str
    configured: bool
    source: ConfigSource
    #: Last few characters only, e.g. "…AB12"; never the full value.
    masked_suffix: str | None = None


def mask(value: str | None) -> str | None:
    """Return a masked suffix like ``…AB12`` (last 4 chars), or None."""
    if not value:
        return None
    tail = value[-4:] if len(value) >= 4 else value
    return f"…{tail}"


def keyring_available() -> bool:
    return _KEYRING_AVAILABLE


# ---- File-store fallback -------------------------------------------------


def _read_file_store() -> dict[str, str]:
    secrets_file = _secrets_file()
    if not secrets_file.exists():
        return {}
    try:
        data = json.loads(secrets_file.read_text(encoding="utf-8"))
        return {k: str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_file_store(store: dict[str, str]) -> None:
    secrets_file = _secrets_file()
    secrets_file.parent.mkdir(parents=True, exist_ok=True)
    secrets_file.write_text(json.dumps(store, indent=2), encoding="utf-8")
    # Best-effort tighten permissions (no-op semantics vary on Windows).
    with contextlib.suppress(OSError):
        secrets_file.chmod(0o600)


# ---- Read / write --------------------------------------------------------


def _dotenv_value(key: str) -> str | None:
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if not env_file.exists():
        return None
    try:
        from dotenv import dotenv_values

        return dotenv_values(env_file).get(key)
    except Exception:  # noqa: BLE001
        return None


def resolve_secret(key: str) -> tuple[str | None, ConfigSource]:
    """Return (value, source) using the documented priority. May return None."""
    env_val = os.environ.get(key)
    if env_val and not looks_like_placeholder(env_val):
        return env_val, ConfigSource.ENVIRONMENT

    if _KEYRING_AVAILABLE:
        try:
            kr_val = keyring.get_password(_KEYRING_SERVICE, key)
        except Exception:  # noqa: BLE001
            kr_val = None
        if kr_val and not looks_like_placeholder(kr_val):
            return kr_val, ConfigSource.CREDENTIAL_STORE

    with _lock:
        file_val = _read_file_store().get(key)
    if file_val and not looks_like_placeholder(file_val):
        return file_val, ConfigSource.FILE

    dotenv_val = _dotenv_value(key)
    if dotenv_val and not looks_like_placeholder(dotenv_val):
        return dotenv_val, ConfigSource.DOTENV

    return None, ConfigSource.NONE


def store_secret(key: str, value: str) -> ConfigSource:
    """Persist a secret, preferring the OS credential store. Returns the source."""
    value = value.strip()
    if _KEYRING_AVAILABLE:
        try:
            keyring.set_password(_KEYRING_SERVICE, key, value)
            return ConfigSource.CREDENTIAL_STORE
        except Exception:  # noqa: BLE001 - fall through to file store
            pass
    with _lock:
        store = _read_file_store()
        store[key] = value
        _write_file_store(store)
    return ConfigSource.FILE


def delete_secret(key: str) -> bool:
    """Remove a stored secret from keyring and the file store.

    Returns True if anything was removed. Values coming from the environment or
    .env cannot be deleted here (the caller should surface that).
    """
    removed = False
    if _KEYRING_AVAILABLE:
        try:
            keyring.delete_password(_KEYRING_SERVICE, key)
            removed = True
        except Exception:  # noqa: BLE001
            pass
    with _lock:
        store = _read_file_store()
        if key in store:
            del store[key]
            _write_file_store(store)
            removed = True
    return removed


def secret_status(key: str) -> SecretStatus:
    """Return a non-sensitive status for a secret key."""
    value, source = resolve_secret(key)
    return SecretStatus(
        key=key,
        configured=value is not None,
        source=source,
        masked_suffix=mask(value) if value is not None else None,
    )
