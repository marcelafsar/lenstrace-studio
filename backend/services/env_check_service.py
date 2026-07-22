"""Environment / configuration checker shared by the CLI and the API route.

Produces a structured report of PASS/WARN/FAIL checks across the desktop
runtime, general configuration, both bots, and the three delivery providers.
Never includes secret values in any output.
"""

from __future__ import annotations

import shutil
import socket
import sys
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from backend.services import (
    apple_devices_service,
    bot_config_service,
    icloud_photos_service,
    pairdrop_service,
    secrets_service,
    settings_service,
)
from core.config.models import BotKind
from core.config.validation import looks_like_placeholder, parse_optional_int
from core.delivery.validation import validate_external_url

_REPO_ROOT = Path(__file__).resolve().parents[2]


class CheckStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class CheckResult(BaseModel):
    name: str
    status: CheckStatus
    category: str
    detail: str = ""
    #: True when this failure indicates invalid configuration (CLI exit code 2).
    config_invalid: bool = False


class CheckReport(BaseModel):
    results: list[CheckResult] = Field(default_factory=list)
    passed: int = 0
    warned: int = 0
    failed: int = 0
    config_invalid: bool = False

    def add(self, result: CheckResult) -> None:
        self.results.append(result)
        if result.status == CheckStatus.PASS:
            self.passed += 1
        elif result.status == CheckStatus.WARN:
            self.warned += 1
        else:
            self.failed += 1
            if result.config_invalid:
                self.config_invalid = True


def _ok(name: str, category: str, detail: str = "") -> CheckResult:
    return CheckResult(name=name, status=CheckStatus.PASS, category=category, detail=detail)


def _warn(name: str, category: str, detail: str = "") -> CheckResult:
    return CheckResult(name=name, status=CheckStatus.WARN, category=category, detail=detail)


def _fail(
    name: str, category: str, detail: str = "", *, config_invalid: bool = False
) -> CheckResult:
    return CheckResult(
        name=name,
        status=CheckStatus.FAIL,
        category=category,
        detail=detail,
        config_invalid=config_invalid,
    )


# ---- Individual check groups --------------------------------------------


def _check_core(report: CheckReport) -> None:
    cat = "core"
    v = sys.version_info
    if v >= (3, 10):
        report.add(_ok("Python version", cat, f"{v.major}.{v.minor}.{v.micro}"))
    else:
        report.add(_fail("Python version", cat, "Python 3.10+ required.", config_invalid=True))

    report.add(
        _ok("Node.js available", cat)
        if shutil.which("node")
        else _warn("Node.js available", cat, "Not found on PATH (needed for the desktop app).")
    )
    report.add(
        _ok("npm available", cat)
        if (shutil.which("npm") or shutil.which("npm.cmd"))
        else _warn("npm available", cat, "Not found on PATH.")
    )

    missing = [m for m in ("fastapi", "uvicorn", "pydantic", "PIL", "piexif") if not _importable(m)]
    report.add(
        _ok("Python dependencies", cat)
        if not missing
        else _fail("Python dependencies", cat, f"Missing: {', '.join(missing)}")
    )

    desktop = _REPO_ROOT / "desktop"
    report.add(
        _ok("Desktop package present", cat)
        if (desktop / "package.json").is_file()
        else _fail("Desktop package present", cat, "desktop/package.json missing.")
    )
    report.add(
        _ok("Node dependencies installed", cat)
        if (desktop / "node_modules").is_dir()
        else _warn("Node dependencies installed", cat, "Run 'npm install' in desktop/.")
    )

    report.add(
        _ok("Backend can bind loopback", cat)
        if _can_bind_loopback()
        else _fail("Backend can bind loopback", cat, "Could not bind 127.0.0.1.")
    )

    for folder in ("core", "backend", "bots", "desktop"):
        exists = (_REPO_ROOT / folder).is_dir()
        report.add(
            _ok(f"Folder {folder}/", cat)
            if exists
            else _fail(f"Folder {folder}/", cat, "Missing project folder.")
        )


def _check_general(report: CheckReport) -> None:
    cat = "general"
    env_file = _REPO_ROOT / ".env"
    example = _REPO_ROOT / ".env.example"

    report.add(
        _ok(".env or environment present", cat)
        if env_file.exists()
        else _warn(".env or environment present", cat, "No .env file (env vars may still be set).")
    )
    report.add(
        _ok(".env.example present", cat)
        if example.is_file()
        else _fail(".env.example present", cat, "Missing .env.example.")
    )
    report.add(_env_ignored_check(cat))

    config = settings_service.get_config()
    report.add(
        _ok("Upload limit valid", cat, f"{config.max_upload_mb} MB")
        if config.max_upload_mb > 0
        else _fail(
            "Upload limit valid", cat, "MAX_UPLOAD_MB must be positive.", config_invalid=True
        )
    )
    report.add(
        _ok("Session timeout valid", cat, f"{config.session_timeout_minutes} min")
        if config.session_timeout_minutes > 0
        else _fail(
            "Session timeout valid", cat, "Invalid SESSION_TIMEOUT_MINUTES.", config_invalid=True
        )
    )
    report.add(
        _ok("Geocoding user agent", cat)
        if config.geocoding_user_agent.strip()
        else _warn("Geocoding user agent", cat, "GEOCODING_USER_AGENT is empty.")
    )


def _check_bot(report: CheckReport, kind: BotKind, strict: bool, connectivity: bool) -> None:
    cat = kind.value
    config = settings_service.get_config()
    bot_settings = config.telegram if kind == BotKind.TELEGRAM else config.discord
    token, source = bot_config_service.resolve_token(kind)

    label = f"{kind.value.capitalize()} token configured"
    if token is None:
        # `resolve_token` returns None for placeholders too, so peek the raw
        # environment value to distinguish "left a placeholder" from "unset".
        raw = _raw_env_token(kind)
        if raw is not None and looks_like_placeholder(raw):
            report.add(_fail(label, cat, "Token looks like a placeholder — replace it."))
        elif strict and bot_settings.enabled:
            report.add(_fail(label, cat, "Enabled bot has no token."))
        else:
            report.add(_warn(label, cat, "No token configured (optional)."))
        return
    report.add(_ok(label, cat, f"source: {source.value}"))

    if kind == BotKind.DISCORD and bot_settings.guild_id:
        gid = parse_optional_int(bot_settings.guild_id)
        report.add(
            _ok("Discord guild id valid", cat)
            if gid is not None
            else _fail(
                "Discord guild id valid",
                cat,
                "DISCORD_GUILD_ID is not numeric.",
                config_invalid=True,
            )
        )

    if connectivity:
        result = bot_config_service.validate_token(kind, token=token)
        if result.valid and result.identity:
            name = result.identity.username or result.identity.bot_id or "resolved"
            report.add(_ok(f"{kind.value.capitalize()} identity", cat, f"@{name}"))
        else:
            report.add(
                _fail(f"{kind.value.capitalize()} identity", cat, result.error or "Invalid.")
            )


def _check_delivery(report: CheckReport) -> None:
    cat = "delivery"
    icloud = icloud_photos_service.ICloudPhotosProvider().availability()
    report.add(
        _ok("iCloud Photos", cat, icloud.summary)
        if icloud.level.value == "ready"
        else _warn("iCloud Photos", cat, icloud.summary)
    )

    config = settings_service.get_config().delivery
    try:
        validate_external_url(config.pairdrop_url)
        report.add(_ok("PairDrop URL valid", cat, config.pairdrop_url))
    except Exception:  # noqa: BLE001
        report.add(
            _fail(
                "PairDrop URL valid",
                cat,
                "Configured PAIRDROP_URL is not a safe URL.",
                config_invalid=True,
            )
        )
    cli = pairdrop_service.detect_cli()
    report.add(
        _ok("PairDrop CLI", cat, "detected")
        if cli
        else _warn("PairDrop CLI", cat, "optional; not found")
    )

    detected = apple_devices_service.detect_apple_devices()
    report.add(
        _ok("Apple Devices", cat, "detected")
        if detected
        else _warn("Apple Devices", cat, "Open Apple Devices to confirm the connected iPhone.")
    )
    report.add(_sync_folder_check(cat))


def _check_geocoding(report: CheckReport) -> None:
    cat = "geocoding"
    geo = settings_service.get_config().geocoding
    if not geo.enabled:
        report.add(_warn("Address search", cat, "Disabled; manual coordinates still work."))
        return
    report.add(_ok("Address search", cat, f"enabled ({geo.provider})"))
    report.add(
        _ok("Geocoding user agent", cat)
        if geo.user_agent.strip()
        else _warn(
            "Geocoding user agent", cat, "GEOCODING_USER_AGENT is empty (required by policy)."
        )
    )


# ---- Small helpers -------------------------------------------------------


def _raw_env_token(kind: BotKind) -> str | None:
    """Peek the raw environment token value (bypassing placeholder filtering)."""
    import os

    return os.environ.get(bot_config_service.token_key(kind))


def _importable(module: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(module) is not None


def _can_bind_loopback() -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
        return True
    except OSError:
        return False


def _env_ignored_check(cat: str) -> CheckResult:
    """Confirm .env is git-ignored (best-effort via git check-ignore)."""
    env_file = _REPO_ROOT / ".env"
    if not env_file.exists():
        return _ok(".env is git-ignored", cat, "no .env present")
    git = shutil.which("git")
    if not git:
        return _warn(".env is git-ignored", cat, "git not available to verify.")
    try:
        import subprocess

        result = subprocess.run(  # noqa: S603 - fixed args, no shell
            [git, "check-ignore", ".env"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            timeout=10,
            shell=False,
        )
        if result.returncode == 0:
            return _ok(".env is git-ignored", cat)
        return _fail(".env is git-ignored", cat, ".env is NOT ignored — do not commit it!")
    except (OSError, subprocess.SubprocessError):
        return _warn(".env is git-ignored", cat, "Could not verify.")


def _sync_folder_check(cat: str) -> CheckResult:
    folder = apple_devices_service.default_sync_folder()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".lenstrace_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return _ok("LensTrace Sync folder writable", cat, folder.name)
    except OSError:
        return _fail("LensTrace Sync folder writable", cat, "Cannot write to the sync folder.")


# ---- Entry point ---------------------------------------------------------


def run_checks(
    *,
    service: str = "all",
    strict: bool = False,
    connectivity: bool = False,
) -> CheckReport:
    """Run the selected checks and return a structured report."""
    report = CheckReport()
    service = service.lower()

    if service in ("all",):
        _check_core(report)
        _check_general(report)
    if service in ("all", "telegram"):
        _check_bot(report, BotKind.TELEGRAM, strict, connectivity)
    if service in ("all", "discord"):
        _check_bot(report, BotKind.DISCORD, strict, connectivity)
    if service in ("all", "delivery"):
        _check_delivery(report)
    if service in ("all", "geocoding"):
        _check_geocoding(report)

    # Ensure secrets never leak into the report.
    _assert_no_secrets(report)
    return report


def _assert_no_secrets(report: CheckReport) -> None:
    tokens = [
        secrets_service.resolve_secret("TELEGRAM_BOT_TOKEN")[0],
        secrets_service.resolve_secret("DISCORD_BOT_TOKEN")[0],
    ]
    tokens = [t for t in tokens if t]
    for result in report.results:
        for token in tokens:
            if token and token in result.detail:
                result.detail = "<redacted>"
