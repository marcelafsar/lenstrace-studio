"""Text formatting shared by both bots (message-friendly summaries/diffs).

Kept free of any bot library so it is unit-testable. Never includes raw image
bytes; coordinates appear only when the user explicitly set them.
"""

from __future__ import annotations

from core.metadata_models import ChangeDiff, MetadataSummary

CAPTURE_DISCLAIMER = (
    "⚠️ Metadata is editable and does NOT prove when, where, or how an image was "
    "actually captured."
)


def format_summary(summary: MetadataSummary) -> str:
    """Render a metadata summary as a compact plain-text block."""
    lines = [
        f"Format: {summary.image_format.value}",
        (
            f"Size: {summary.width}×{summary.height}"
            if summary.width and summary.height
            else "Size: unknown"
        ),
        f"Make: {summary.make or '—'}",
        f"Model: {summary.model or '—'}",
        f"Lens: {summary.lens_model or '—'}",
        f"Software: {summary.software or '—'}",
        f"Date taken: {summary.datetime_original or '—'}",
        f"UTC offset: {summary.offset_time_original or '—'}",
        f"GPS: {'present' if summary.has_gps else 'none'}",
    ]
    return "\n".join(lines)


def format_diff(diff: ChangeDiff) -> str:
    """Render a before/after diff as a plain-text list keyed by status."""
    if not diff.rows:
        return "No changes."
    symbols = {"added": "＋", "changed": "→", "removed": "－", "preserved": "·"}
    lines = []
    for row in diff.rows:
        sym = symbols.get(row.status, "·")
        if row.status == "preserved":
            continue
        lines.append(f"{sym} {row.field}: {row.original or '—'} → {row.new or '—'}")
    return "\n".join(lines) if lines else "No changes."
