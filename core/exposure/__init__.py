"""Simulated camera-exposure profiles and the exposure resolver.

This package owns everything about *generated* exposure metadata so desktop,
Telegram, and Discord all behave identically. Nothing here is claimed to be a
real measurement: values produced from a profile are always labelled
"Simulated exposure metadata" and recorded as such in the audit report.
"""

from __future__ import annotations

from core.exposure.calculations import aperture_value_apex, shutter_speed_value_apex
from core.exposure.loader import get_default_profile_loader
from core.exposure.models import (
    ExposureMode,
    ExposureProfile,
    FieldSource,
    ResolvedExposure,
)
from core.exposure.resolver import resolve_exposure

__all__ = [
    "ExposureMode",
    "ExposureProfile",
    "FieldSource",
    "ResolvedExposure",
    "aperture_value_apex",
    "shutter_speed_value_apex",
    "get_default_profile_loader",
    "resolve_exposure",
]
