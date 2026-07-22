"""Translate a bot session's free-form config into engine plan kwargs.

Shared by both bots so Telegram and Discord build identical change plans from
the same choices (exposure simulation + output resolution).
"""

from __future__ import annotations

from typing import Any


def exposure_resolution_kwargs(cfg: dict[str, Any]) -> dict[str, Any]:
    """Return the exposure + resolution keyword arguments for build_change_plan."""
    from core.exposure.models import ExposureMode
    from core.imaging.resolution_models import FitMode, ResolutionMode

    mode = cfg.get("exposure_mode")
    return {
        "exposure_mode": ExposureMode(mode) if mode else None,
        "exposure_profile_id": cfg.get("exposure_profile_id"),
        "exposure_custom": cfg.get("exposure_custom"),
        "resolution_mode": ResolutionMode(cfg.get("resolution_mode", "keep")),
        "resolution_fit": FitMode(cfg.get("resolution_fit", "crop_to_fill")),
        "custom_width": cfg.get("custom_width"),
        "custom_height": cfg.get("custom_height"),
    }
