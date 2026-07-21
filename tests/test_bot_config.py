"""Tests for the bot config service (status, validation, settings)."""

from __future__ import annotations

import time

from backend.services import bot_config_service, secrets_service, settings_service
from backend.services.bot_config_service import BotIdentity, BotValidation
from core.config.models import BotKind

_FAKE = "123456:ABCDEF_fake_token_value_1234567890aa"


def test_status_when_unconfigured(isolated_state):
    status = bot_config_service.get_status(BotKind.TELEGRAM)
    assert status.token_configured is False
    assert status.token_masked_suffix is None


def test_save_and_status_masked(isolated_state, monkeypatch):
    monkeypatch.setattr(secrets_service, "_KEYRING_AVAILABLE", False)
    bot_config_service.save_token(BotKind.TELEGRAM, _FAKE)
    status = bot_config_service.get_status(BotKind.TELEGRAM)
    assert status.token_configured
    assert status.token_masked_suffix and _FAKE not in status.token_masked_suffix


def test_validate_with_injected_validator(isolated_state):
    def fake_validator(kind, token):
        assert token == _FAKE
        return BotValidation(valid=True, identity=BotIdentity(username="LensBot", bot_id="42"))

    result = bot_config_service.validate_token(
        BotKind.DISCORD, token=_FAKE, validator=fake_validator
    )
    assert result.valid
    assert result.identity.username == "LensBot"


def test_validate_no_token(isolated_state):
    # Space out from any prior validation to avoid the rate limiter.
    time.sleep(0)
    result = bot_config_service.validate_token(
        BotKind.TELEGRAM, token=None, validator=lambda k, t: BotValidation(valid=True)
    )
    assert result.valid is False
    assert "token" in (result.error or "").lower()


def test_validate_rate_limited(isolated_state):
    # Reset the module-global rate-limit clock so the first call is not limited.
    bot_config_service._last_validation.clear()
    ok = BotValidation(valid=True, identity=BotIdentity(username="x"))
    first = bot_config_service.validate_token(
        BotKind.TELEGRAM, token=_FAKE, validator=lambda k, t: ok
    )
    second = bot_config_service.validate_token(
        BotKind.TELEGRAM, token=_FAKE, validator=lambda k, t: ok
    )
    # Two rapid calls: the second is rate-limited.
    assert first.valid is True
    assert second.valid is False


def test_settings_override_persists(isolated_state):
    settings_service.set_bot_setting(BotKind.TELEGRAM, "auto_start", True)
    assert settings_service.get_config().telegram.auto_start is True
    settings_service.set_bot_setting(BotKind.TELEGRAM, "auto_start", False)
    assert settings_service.get_config().telegram.auto_start is False


def test_validate_error_never_contains_token(isolated_state):
    def boom(kind, token):
        raise RuntimeError(f"boom with {token}")

    result = bot_config_service.validate_token(BotKind.DISCORD, token=_FAKE, validator=boom)
    assert result.valid is False
    assert _FAKE not in (result.error or "")
