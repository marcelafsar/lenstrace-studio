"""Compute output dimensions and perform high-quality, honest resizes.

Never stretches: a non-matching aspect ratio is reconciled by cropping to fill
or fitting with padding, chosen by the caller. Upscaling changes pixel
dimensions but is transparently *not* claimed to recover real detail — the UI
copy states this and the audit report records the transform.
"""

from __future__ import annotations

from pathlib import Path

from core.exceptions import LensTraceError
from core.imaging.resolution_models import (
    IPHONE_12MP_LONG,
    IPHONE_12MP_SHORT,
    FitMode,
    ResolutionMode,
    ResolutionPlan,
)


class ResolutionError(LensTraceError):
    """Raised for invalid resolution requests."""


_MIN_DIMENSION = 1
_MAX_DIMENSION = 30000


def compute_output_dimensions(
    source_width: int,
    source_height: int,
    *,
    mode: ResolutionMode,
    fit: FitMode = FitMode.CROP_TO_FILL,
    custom_width: int | None = None,
    custom_height: int | None = None,
) -> ResolutionPlan:
    """Resolve the requested resolution mode into concrete output dimensions."""
    if mode == ResolutionMode.KEEP:
        out_w, out_h = source_width, source_height
    elif mode == ResolutionMode.IPHONE_12MP:
        # Portrait vs. landscape follows the source's orientation.
        if source_height >= source_width:
            out_w, out_h = IPHONE_12MP_SHORT, IPHONE_12MP_LONG
        else:
            out_w, out_h = IPHONE_12MP_LONG, IPHONE_12MP_SHORT
    elif mode == ResolutionMode.CUSTOM:
        if custom_width is None or custom_height is None:
            raise ResolutionError(
                "Custom resolution requires width and height",
                user_message="Enter both a width and a height for custom resolution.",
            )
        _validate_dimension(custom_width)
        _validate_dimension(custom_height)
        out_w, out_h = custom_width, custom_height
    else:  # pragma: no cover - exhaustive
        raise ResolutionError(f"Unknown resolution mode: {mode}")

    return ResolutionPlan(
        mode=mode,
        fit=fit,
        output_width=out_w,
        output_height=out_h,
        source_width=source_width,
        source_height=source_height,
    )


def _validate_dimension(value: int) -> None:
    if not _MIN_DIMENSION <= value <= _MAX_DIMENSION:
        raise ResolutionError(
            f"Dimension out of range: {value}",
            user_message=f"Dimensions must be between {_MIN_DIMENSION} and {_MAX_DIMENSION} px.",
        )


def resize_image(image, plan: ResolutionPlan):
    """Return a new PIL image at ``plan`` dimensions, never stretched.

    CROP_TO_FILL scales to cover the target then centre-crops the overflow.
    FIT_WITH_PADDING scales to fit inside the target then pads (black) the rest.
    Uses Lanczos resampling for quality.
    """
    from PIL import Image, ImageOps

    target_w, target_h = plan.output_width, plan.output_height
    if not plan.changes_dimensions:
        return image.copy()

    src_w, src_h = image.size
    if plan.fit == FitMode.CROP_TO_FILL:
        # ImageOps.fit scales-to-cover then centre-crops — no distortion.
        return ImageOps.fit(image, (target_w, target_h), method=Image.Resampling.LANCZOS)

    # FIT_WITH_PADDING: preserve the whole image, pad to the target.
    scale = min(target_w / src_w, target_h / src_h)
    new_w = max(1, round(src_w * scale))
    new_h = max(1, round(src_h * scale))
    resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    background = Image.new("RGB", (target_w, target_h), (0, 0, 0))
    offset = ((target_w - new_w) // 2, (target_h - new_h) // 2)
    background.paste(resized, offset)
    return background


def load_and_resize(source: Path, plan: ResolutionPlan, dest: Path, *, quality: int = 95) -> None:
    """Load ``source``, resize per ``plan``, and save a JPEG to ``dest``."""
    from PIL import Image

    try:
        with Image.open(source) as img:
            rgb = img.convert("RGB")
            out = resize_image(rgb, plan)
            if out.size != (plan.output_width, plan.output_height):  # pragma: no cover
                raise ResolutionError(
                    f"Resize produced {out.size}, expected "
                    f"{(plan.output_width, plan.output_height)}",
                    user_message="The image could not be resized to the requested dimensions.",
                )
            out.save(dest, format="JPEG", quality=quality, subsampling=0)
    except ResolutionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ResolutionError(
            f"Resize failed: {exc}",
            user_message="The image could not be resized.",
        ) from exc
