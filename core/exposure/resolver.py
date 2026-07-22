"""Resolve an exposure mode + profile + source into concrete values to write.

This is the single place that decides which exposure fields an export will
carry and where each one came from. Desktop, Telegram, and Discord all call it,
so their outputs are identical for the same inputs.
"""

from __future__ import annotations

from core.exposure.models import (
    ExposureMode,
    ExposureProfile,
    FieldSource,
    ResolvedExposure,
)

#: Fields a profile contributes, in the order they appear in the report.
_PROFILE_FIELDS = (
    "iso",
    "exposure_time_seconds",
    "exposure_bias",
    "flash",
    "exposure_program",
    "metering_mode",
    "white_balance",
    "exposure_mode_exif",
    "scene_capture_type",
    "light_source",
)


def _profile_values(profile: ExposureProfile) -> dict[str, object]:
    return {
        "iso": profile.iso,
        "exposure_time_seconds": profile.exposure_time_seconds,
        "exposure_bias": profile.exposure_bias,
        "flash": profile.flash,
        "exposure_program": profile.exposure_program,
        "metering_mode": profile.metering_mode,
        "white_balance": profile.white_balance,
        "exposure_mode_exif": profile.exposure_mode_exif,
        "scene_capture_type": profile.scene_capture_type,
        "light_source": profile.light_source,
    }


def resolve_exposure(
    *,
    mode: ExposureMode,
    profile: ExposureProfile | None,
    source_iso: int | None = None,
    source_exposure_time_seconds: float | None = None,
    source_exposure_bias: float | None = None,
    custom: dict | None = None,
) -> ResolvedExposure:
    """Compute the concrete exposure fields to write and their provenance.

    ``source_*`` are the values already present in the source image (used by
    PRESERVE and FILL_MISSING). ``custom`` maps field names to user-entered
    values (used by CUSTOM). A profile is required for FILL_MISSING and OVERRIDE.
    """
    resolved = ResolvedExposure(mode=mode)
    sources: dict[str, FieldSource] = {}

    if mode == ExposureMode.PRESERVE:
        # Nothing is generated; existing source values survive via the base EXIF
        # copy. We only record the ones we know exist, for the report.
        if source_iso is not None:
            sources["iso"] = FieldSource.PRESERVED
        if source_exposure_time_seconds is not None:
            sources["exposure_time_seconds"] = FieldSource.PRESERVED
        if source_exposure_bias is not None:
            sources["exposure_bias"] = FieldSource.PRESERVED
        resolved.sources = sources
        return resolved

    if mode == ExposureMode.CUSTOM:
        custom = custom or {}
        for field in _PROFILE_FIELDS:
            if field in custom and custom[field] is not None:
                setattr(resolved, field, custom[field])
                sources[field] = FieldSource.CUSTOM
        resolved.sources = sources
        return resolved

    if profile is None:
        raise ValueError(f"mode {mode} requires an exposure profile")

    values = _profile_values(profile)
    resolved.profile_id = profile.id
    resolved.profile_display_name = profile.display_name

    if mode == ExposureMode.OVERRIDE:
        for field, value in values.items():
            setattr(resolved, field, value)
            if value is not None:
                sources[field] = FieldSource.SIMULATED
        resolved.is_simulated = True

    elif mode == ExposureMode.FILL_MISSING:
        existing = {
            "iso": source_iso,
            "exposure_time_seconds": source_exposure_time_seconds,
            "exposure_bias": source_exposure_bias,
        }
        for field, value in values.items():
            source_value = existing.get(field)
            if source_value is not None:
                setattr(resolved, field, source_value)
                sources[field] = FieldSource.PRESERVED
            elif value is not None:
                setattr(resolved, field, value)
                sources[field] = FieldSource.SIMULATED
                resolved.is_simulated = True
    else:  # pragma: no cover - exhaustive
        raise ValueError(f"Unhandled exposure mode: {mode}")

    resolved.sources = sources
    return resolved
