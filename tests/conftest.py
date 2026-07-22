"""Shared pytest fixtures.

Test images are generated on the fly (a tiny solid-colour JPEG) so we never
commit real photos or personal metadata to the repository.
"""

from __future__ import annotations

from pathlib import Path

import piexif
import pytest
from PIL import Image

from core.metadata_engine import MetadataEngine


def _make_jpeg(path: Path, *, with_exif: bool = True) -> Path:
    """Create a small JPEG, optionally with some baseline EXIF."""
    img = Image.new("RGB", (48, 32), color=(90, 120, 160))
    if with_exif:
        exif = {
            "0th": {
                piexif.ImageIFD.Make: b"OldMake",
                piexif.ImageIFD.Model: b"OldModel",
                piexif.ImageIFD.DateTime: b"2020:01:01 08:00:00",
            },
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: b"2020:01:01 08:00:00",
            },
            "GPS": {},
            "1st": {},
            "Interop": {},
            "thumbnail": None,
        }
        img.save(path, format="JPEG", quality=95, exif=piexif.dump(exif))
    else:
        img.save(path, format="JPEG", quality=95)
    return path


@pytest.fixture
def sample_jpeg(tmp_path: Path) -> Path:
    return _make_jpeg(tmp_path / "sample.jpg", with_exif=True)


@pytest.fixture
def bare_jpeg(tmp_path: Path) -> Path:
    return _make_jpeg(tmp_path / "bare.jpg", with_exif=False)


@pytest.fixture
def png_image(tmp_path: Path) -> Path:
    path = tmp_path / "image.png"
    Image.new("RGB", (40, 40), color=(10, 200, 10)).save(path, format="PNG")
    return path


@pytest.fixture
def large_jpeg(tmp_path: Path) -> Path:
    """A JPEG at genuine iPhone 13 Pro Max resolution (12 MP, 3:4)."""
    path = tmp_path / "large.jpg"
    Image.new("RGB", (3024, 4032), color=(80, 100, 120)).save(path, format="JPEG", quality=90)
    return path


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    d = tmp_path / "out"
    d.mkdir()
    return d


@pytest.fixture
def engine() -> MetadataEngine:
    return MetadataEngine()


@pytest.fixture
def isolated_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point secret/state storage at a temp dir so tests never touch ~/.lenstrace.

    Also clears the settings cache so env changes take effect.
    """
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("LENSTRACE_SECRETS_DIR", str(state / "secrets"))
    monkeypatch.setenv("LENSTRACE_STATE_DIR", str(state / "settings"))
    # Ensure no ambient bot tokens leak in from the real environment.
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    from backend.services import settings_service

    settings_service.reload_config()
    yield state
    settings_service.reload_config()
