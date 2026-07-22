"""Tests for the environment checker service and CLI behaviour."""

from __future__ import annotations

import json

from backend.services import secrets_service
from backend.services.env_check_service import CheckStatus, run_checks
from core.config.models import BotKind


def test_run_checks_returns_report(isolated_state):
    report = run_checks(service="all")
    assert report.results
    # Core Python-version check must pass in this environment.
    assert any(r.name == "Python version" and r.status == CheckStatus.PASS for r in report.results)


def test_report_json_has_no_ansi(isolated_state):
    report = run_checks(service="delivery")
    dumped = report.model_dump_json()
    assert "\033" not in dumped
    json.loads(dumped)  # must be valid JSON


def test_missing_token_is_warning_in_non_strict(isolated_state):
    report = run_checks(service="telegram", strict=False)
    statuses = {r.name: r.status for r in report.results}
    assert statuses.get("Telegram token configured") == CheckStatus.WARN


def test_placeholder_token_fails(isolated_state, monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "your-token-here")
    report = run_checks(service="discord")
    assert any(
        r.name == "Discord token configured" and r.status == CheckStatus.FAIL
        for r in report.results
    )


def test_no_secret_appears_in_report(isolated_state, monkeypatch):
    fake = "111222:SECRETVALUE_should_not_appear_9999"
    monkeypatch.setattr(secrets_service, "_KEYRING_AVAILABLE", False)
    secrets_service.store_secret("TELEGRAM_BOT_TOKEN", fake)
    report = run_checks(service="telegram")
    assert fake not in report.model_dump_json()


def test_delivery_checks_present(isolated_state):
    report = run_checks(service="delivery")
    names = {r.name for r in report.results}
    assert "PairDrop URL valid" in names
    assert "LensTrace Sync folder writable" in names


def test_invalid_pairdrop_url_is_config_invalid(isolated_state, monkeypatch):
    monkeypatch.setenv("PAIRDROP_URL", "javascript:bad")
    from backend.services import settings_service

    settings_service.reload_config()
    report = run_checks(service="delivery")
    assert report.config_invalid is True


def test_connectivity_uses_injected_bot_validation(isolated_state, monkeypatch):
    # Ensure a configured, non-placeholder token so the connectivity branch runs.
    monkeypatch.setattr(secrets_service, "_KEYRING_AVAILABLE", False)
    secrets_service.store_secret("TELEGRAM_BOT_TOKEN", "123456:ABCDEF_fake_1234567890")

    from backend.services import bot_config_service
    from backend.services.bot_config_service import BotIdentity, BotValidation

    monkeypatch.setattr(
        bot_config_service,
        "validate_token",
        lambda kind, token=None: BotValidation(
            valid=True, identity=BotIdentity(username="LensBot")
        ),
    )
    report = run_checks(service="telegram", connectivity=True)
    assert any("identity" in r.name.lower() for r in report.results)
    _ = BotKind  # imported for clarity of the tested surface


def test_geocoding_check_present(isolated_state):
    from backend.services.env_check_service import run_checks

    report = run_checks(service="geocoding")
    names = {r.name for r in report.results}
    assert "Address search" in names


def test_geocoding_disabled_is_warning(isolated_state, monkeypatch):
    monkeypatch.setenv("GEOCODING_ENABLED", "false")
    from backend.services import settings_service
    from backend.services.env_check_service import CheckStatus, run_checks

    settings_service.reload_config()
    report = run_checks(service="geocoding")
    statuses = {r.name: r.status for r in report.results}
    assert statuses.get("Address search") == CheckStatus.WARN
