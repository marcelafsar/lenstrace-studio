"""Bot Control Center endpoints.

All routes sit behind the session-token dependency (applied where the router is
included). No secret value is ever returned; only masked status is exposed.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.services import bot_config_service, settings_service
from backend.services.bot_config_service import BotIdentity, BotValidation
from backend.services.bot_supervisor import get_supervisor
from core.bots.status import BotRuntimeStatus
from core.config.models import BotKind, ConfigSource

router = APIRouter(prefix="/bots", tags=["bots"])


class BotView(BaseModel):
    kind: BotKind
    enabled: bool
    auto_start: bool
    guild_id: str | None = None
    token_configured: bool
    token_source: ConfigSource
    token_masked_suffix: str | None = None
    identity: BotIdentity | None = None
    runtime: BotRuntimeStatus


class BotListResponse(BaseModel):
    bots: list[BotView]


class ValidateRequest(BaseModel):
    #: Optional token to test before saving. Never echoed back.
    token: str | None = None


class SaveTokenRequest(BaseModel):
    token: str


class UpdateSettingsRequest(BaseModel):
    enabled: bool | None = None
    auto_start: bool | None = None
    guild_id: str | None = None


class LogsResponse(BaseModel):
    logs: list[str]


def _kind(bot_id: str) -> BotKind:
    try:
        return BotKind(bot_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown bot.") from exc


def _view(kind: BotKind) -> BotView:
    cfg = bot_config_service.get_status(kind)
    runtime = get_supervisor().status(kind)
    return BotView(
        kind=kind,
        enabled=cfg.enabled,
        auto_start=cfg.auto_start,
        guild_id=cfg.guild_id,
        token_configured=cfg.token_configured,
        token_source=cfg.token_source,
        token_masked_suffix=cfg.token_masked_suffix,
        identity=cfg.identity,
        runtime=runtime,
    )


@router.get("", response_model=BotListResponse)
def list_bots() -> BotListResponse:
    return BotListResponse(bots=[_view(BotKind.TELEGRAM), _view(BotKind.DISCORD)])


@router.get("/{bot_id}", response_model=BotView)
def get_bot(bot_id: str) -> BotView:
    return _view(_kind(bot_id))


@router.post("/{bot_id}/validate", response_model=BotValidation)
def validate_bot(bot_id: str, body: ValidateRequest) -> BotValidation:
    kind = _kind(bot_id)
    return bot_config_service.validate_token(kind, token=body.token)


@router.post("/{bot_id}/token", response_model=BotView)
def save_token(bot_id: str, body: SaveTokenRequest) -> BotView:
    kind = _kind(bot_id)
    if not body.token or not body.token.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Please paste a bot token.")
    bot_config_service.save_token(kind, body.token)
    return _view(kind)


@router.delete("/{bot_id}/secret", response_model=BotView)
def clear_token(bot_id: str) -> BotView:
    kind = _kind(bot_id)
    # Stop the bot first if running, since its token is being removed.
    get_supervisor().stop(kind)
    bot_config_service.clear_token(kind)
    return _view(kind)


@router.put("/{bot_id}/settings", response_model=BotView)
def update_settings(bot_id: str, body: UpdateSettingsRequest) -> BotView:
    kind = _kind(bot_id)
    if body.enabled is not None:
        settings_service.set_bot_setting(kind, "enabled", body.enabled)
    if body.auto_start is not None:
        settings_service.set_bot_setting(kind, "auto_start", body.auto_start)
    if body.guild_id is not None:
        settings_service.set_bot_setting(kind, "guild_id", body.guild_id or None)
    return _view(kind)


@router.post("/{bot_id}/start", response_model=BotView)
def start_bot(bot_id: str) -> BotView:
    kind = _kind(bot_id)
    if bot_config_service.resolve_token(kind)[0] is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="This bot has no token configured yet.",
        )
    get_supervisor().start(kind)
    return _view(kind)


@router.post("/{bot_id}/stop", response_model=BotView)
def stop_bot(bot_id: str) -> BotView:
    kind = _kind(bot_id)
    get_supervisor().stop(kind)
    return _view(kind)


@router.post("/{bot_id}/restart", response_model=BotView)
def restart_bot(bot_id: str) -> BotView:
    kind = _kind(bot_id)
    if bot_config_service.resolve_token(kind)[0] is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="This bot has no token configured yet.",
        )
    get_supervisor().restart(kind)
    return _view(kind)


@router.post("/{bot_id}/resync", response_model=BotView)
def resync_commands(bot_id: str) -> BotView:
    """Force a slash-command resync (Discord). Restarts the bot's process."""
    kind = _kind(bot_id)
    if bot_config_service.resolve_token(kind)[0] is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="This bot has no token configured yet.",
        )
    get_supervisor().resync_commands(kind)
    return _view(kind)


@router.get("/{bot_id}/logs", response_model=LogsResponse)
def bot_logs(bot_id: str) -> LogsResponse:
    kind = _kind(bot_id)
    return LogsResponse(logs=get_supervisor().logs(kind))
