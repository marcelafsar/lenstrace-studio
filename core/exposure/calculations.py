"""APEX exposure-value calculations, kept separate so they are unit-testable.

EXIF stores several exposure quantities in the additive APEX (log2) system in
addition to the direct values. LensTrace writes both so viewers that read either
representation stay consistent.
"""

from __future__ import annotations

import math


def aperture_value_apex(f_number: float) -> float:
    """APEX ApertureValue = 2 * log2(FNumber).

    e.g. f/1.5 -> ~1.17.
    """
    if f_number <= 0:
        raise ValueError("f_number must be positive")
    return 2.0 * math.log2(f_number)


def shutter_speed_value_apex(exposure_time_seconds: float) -> float:
    """APEX ShutterSpeedValue = -log2(ExposureTime).

    e.g. 1/121 s -> ~log2(121) = 6.92.
    """
    if exposure_time_seconds <= 0:
        raise ValueError("exposure_time_seconds must be positive")
    return -math.log2(exposure_time_seconds)
