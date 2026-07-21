"""Safe temporary workspaces for bot file processing.

Each workspace is an isolated directory under the system temp root. Filenames
are sanitised via the core validator. Workspaces are always cleaned up after the
response is delivered (use as a context manager or call ``cleanup()``).
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from types import TracebackType

from core.validation import sanitize_filename


class TemporaryWorkspace:
    """An isolated temp directory that deletes itself on exit."""

    def __init__(self, prefix: str = "lenstrace-bot-") -> None:
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
