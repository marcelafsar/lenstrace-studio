"""Load, validate, and cache the simulated exposure-profile library."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from core.exceptions import LensTraceError
from core.exposure.models import ExposureProfile, ProfileLibrary

_DEFAULT_PROFILE_FILE = Path(__file__).with_name("profiles.json")

#: The profile applied by default when auto-fill kicks in.
DEFAULT_PROFILE_ID = "default"


class InvalidProfileError(LensTraceError):
    """Raised when the exposure-profile file is missing or invalid."""


class ProfileLoader:
    """Loads and holds a validated :class:`ProfileLibrary`."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _DEFAULT_PROFILE_FILE
        self._library: ProfileLibrary | None = None

    def load(self) -> ProfileLibrary:
        if self._library is not None:
            return self._library
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise InvalidProfileError(
                f"Exposure profile file not found: {self.path}",
                user_message="The exposure-profile file is missing.",
            ) from exc
        except json.JSONDecodeError as exc:
            raise InvalidProfileError(
                f"Exposure profile file is not valid JSON: {exc}",
                user_message="The exposure-profile file is corrupted.",
            ) from exc
        try:
            library = ProfileLibrary.model_validate(raw)
        except ValidationError as exc:
            raise InvalidProfileError(
                f"Exposure profile file failed validation: {exc}",
                user_message="The exposure-profile file has invalid entries.",
            ) from exc
        self._library = library
        return library

    def list_profiles(self) -> list[ExposureProfile]:
        return self.load().profiles

    def get(self, profile_id: str) -> ExposureProfile:
        profile = self.load().by_id(profile_id)
        if profile is None:
            raise InvalidProfileError(
                f"Unknown exposure profile id: {profile_id!r}",
                user_message=f"Exposure profile '{profile_id}' was not found.",
            )
        return profile


@lru_cache(maxsize=1)
def get_default_profile_loader() -> ProfileLoader:
    """Process-wide cached loader for the bundled profile file."""
    loader = ProfileLoader()
    loader.load()  # validate eagerly so startup fails fast on a bad file
    return loader
