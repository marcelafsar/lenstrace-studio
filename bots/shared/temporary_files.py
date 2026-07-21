"""Safe temporary workspaces for bot file processing.

Each workspace is an isolated directory under the system temp root. Filenames
are sanitised via the core validator. Workspaces are always cleaned up after the
response is delivered (use as a context manager or call ``cleanup()``).
"""

from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path
from types import TracebackType

from core.validation import sanitize_filename

_WORKSPACE_PREFIX = "lenstrace-bot-"
#: Stale workspaces older than this are removed on startup (seconds).
_DEFAULT_RETENTION_S = 6 * 60 * 60


class TemporaryWorkspace:
    """An isolated temp directory that deletes itself on exit.

    The directory name is created by ``tempfile.mkdtemp`` (cryptographically
    unpredictable) under the system temp root, so sessions never collide and
    names are not guessable.
    """

    def __init__(self, prefix: str = _WORKSPACE_PREFIX) -> None:
        self._dir = Path(tempfile.mkdtemp(prefix=prefix))
        self.input_dir = self._dir / "in"
        self.output_dir = self._dir / "out"
        self.input_dir.mkdir()
        self.output_dir.mkdir()

    @property
    def path(self) -> Path:
        return self._dir

    def input_path(self, filename: str) -> Path:
        """Return a sanitised path inside the input dir for a downloaded file."""
        return self.input_dir / sanitize_filename(filename)

    def cleanup(self) -> None:
        shutil.rmtree(self._dir, ignore_errors=True)

    def __enter__(self) -> TemporaryWorkspace:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.cleanup()


def cleanup_stale_workspaces(retention_seconds: int = _DEFAULT_RETENTION_S) -> int:
    """Remove LensTrace bot temp workspaces older than the retention period.

    Only ever touches directories under the system temp root whose names start
    with the LensTrace prefix — never arbitrary system temp files. Returns the
    number of directories removed. Safe to call on bot startup.
    """
    removed = 0
    temp_root = Path(tempfile.gettempdir())
    now = time.time()
    try:
        candidates = list(temp_root.glob(f"{_WORKSPACE_PREFIX}*"))
    except OSError:
        return 0
    for path in candidates:
        if not path.is_dir():
            continue
        try:
            age = now - path.stat().st_mtime
        except OSError:
            continue
        if age > retention_seconds:
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
    return removed
