"""Load, validate, and cache the device preset library."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from core.exceptions import InvalidPresetError
from core.presets.schema import DevicePreset, LensPreset, PresetLibrary, SourceStatus

_DEFAULT_PRESET_FILE = Path(__file__).with_name("iphone_presets.json")

#: Always-available fallback so the UI has at least one safe option.
_GENERIC_APPLE = DevicePreset(
    id="generic-apple-iphone",
    manufacturer="Apple",
    display_name="Generic Apple iPhone",
    generation="Generic",
    exif_model="iPhone",
    software_default=None,
    lenses=[LensPreset(id="main", display_name="Main Camera", lens_model="")],
    notes="Use when the exact model is unknown. Writes only Make=Apple, Model=iPhone.",
    source_status=SourceStatus.GENERIC,
)


class PresetLoader:
    """Loads and holds a validated :class:`PresetLibrary`."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _DEFAULT_PRESET_FILE
        self._library: PresetLibrary | None = None

    def load(self) -> PresetLibrary:
        """Read and validate the preset file, injecting the generic fallback."""
        if self._library is not None:
            return self._library
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise InvalidPresetError(
                f"Preset file not found: {self.path}",
                user_message="The device preset file is missing.",
            ) from exc
        except json.JSONDecodeError as exc:
            raise InvalidPresetError(
                f"Preset file is not valid JSON: {exc}",
                user_message="The device preset file is corrupted.",
            ) from exc

        try:
            library = PresetLibrary.model_validate(raw)
        except ValidationError as exc:
            raise InvalidPresetError(
                f"Preset file failed validation: {exc}",
                user_message="The device preset file has invalid entries.",
            ) from exc

        if library.by_id(_GENERIC_APPLE.id) is None:
            library.devices.insert(0, _GENERIC_APPLE)
        self._library = library
        return library

    def list_devices(self) -> list[DevicePreset]:
        return self.load().devices

    def get(self, preset_id: str) -> DevicePreset:
        device = self.load().by_id(preset_id)
        if device is None:
            raise InvalidPresetError(
                f"Unknown preset id: {preset_id!r}",
                user_message=f"Device preset '{preset_id}' was not found.",
            )
        return device

    def grouped_by_generation(self) -> dict[str, list[DevicePreset]]:
        """Return devices grouped by their ``generation`` label for the UI."""
        groups: dict[str, list[DevicePreset]] = {}
        for device in self.list_devices():
            key = device.generation or "Other"
            groups.setdefault(key, []).append(device)
        return groups


@lru_cache(maxsize=1)
def get_default_loader() -> PresetLoader:
    """Return a process-wide cached loader for the bundled preset file."""
    loader = PresetLoader()
    loader.load()  # validate eagerly so startup fails fast on a bad file
    return loader
