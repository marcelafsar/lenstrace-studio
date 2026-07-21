"""Tests for the secrets service (storage, masking, precedence, deletion)."""

from __future__ import annotations

from backend.services import secrets_service
from core.config.models import ConfigSource

_FAKE = "123456:ABCDEF_this_is_a_fake_test_token_0000"


def test_store_and_resolve_file_fallback(isolated_state, monkeypatch):
    # Force the file-store path (no keyring) for a deterministic test.
    monkeypatch.setattr(secrets_service, "_KEYRING_AVAILABLE", False)
    assert secrets_service.secret_status("TELEGRAM_BOT_TOKEN").configured is False
    source = secrets_service.store_secret("TELEGRAM_BOT_TOKEN", _FAKE)
    assert source == ConfigSource.FILE
    value, resolved_source = secrets_service.resolve_secret("TELEGRAM_BOT_TOKEN")
    assert value == _FAKE
    assert resolved_source == ConfigSource.FILE


def test_mask_hides_most_of_token():
    masked = secrets_service.mask(_FAKE)
    assert masked is not None
    assert _FAKE not in masked
    assert masked.endswith(_FAKE[-4:])
    assert len(masked) <= 6


def test_status_never_exposes_full_value(isolated_state, monkeypatch):
    monkeypatch.setattr(secrets_service, "_KEYRING_AVAILABLE", False)
    secrets_service.store_secret("DISCORD_BOT_TOKEN", _FAKE)
    status = secrets_service.secret_status("DISCORD_BOT_TOKEN")
    assert status.configured
    assert status.masked_suffix and _FAKE not in status.masked_suffix
    # The model dump must not contain the secret.
    assert _FAKE not in status.model_dump_json()


def test_environment_takes_precedence(isolated_state, monkeypatch):
    monkeypatch.setattr(secrets_service, "_KEYRING_AVAILABLE", False)
    secrets_service.store_secret("TELEGRAM_BOT_TOKEN", "file-value")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", _FAKE)
    value, source = secrets_service.resolve_secret("TELEGRAM_BOT_TOKEN")
    assert value == _FAKE
    assert source == ConfigSource.ENVIRONMENT


def test_placeholder_is_ignored(isolated_state, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "changeme")
    value, source = secrets_service.resolve_secret("TELEGRAM_BOT_TOKEN")
    assert value is None
    assert source == ConfigSource.NONE


def test_delete_secret(isolated_state, monkeypatch):
    monkeypatch.setattr(secrets_service, "_KEYRING_AVAILABLE", False)
    secrets_service.store_secret("TELEGRAM_BOT_TOKEN", _FAKE)
    assert secrets_service.delete_secret("TELEGRAM_BOT_TOKEN") is True
    assert secrets_service.secret_status("TELEGRAM_BOT_TOKEN").configured is False
