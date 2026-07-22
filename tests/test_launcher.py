"""Tests for the run_desktop.py launcher helpers.

These test the pure/isolatable pieces of the launcher (port selection, health
polling, dependency checks) without actually spawning uvicorn or Electron.
Importing the module is safe: its top-level code only defines functions and
the ``if __name__ == "__main__"`` guard prevents ``main()`` from running.
"""

from __future__ import annotations

import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run_desktop  # noqa: E402


def test_free_port_returns_bindable_port():
    port = run_desktop.free_port()
    assert 0 < port < 65536
    # The port must be immediately bindable again (released, not held open).
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((run_desktop.HOST, port))


def test_free_port_returns_distinct_ports_when_called_repeatedly():
    ports = {run_desktop.free_port() for _ in range(5)}
    # Not a strict guarantee, but collisions across 5 rapid calls would be
    # exceptionally unlikely and would indicate free_port is broken.
    assert len(ports) >= 4


def test_check_python_deps_true_in_test_env():
    # The test environment has fastapi/uvicorn/pydantic/PIL/piexif installed
    # (they're runtime dependencies), so this must succeed here.
    assert run_desktop.check_python_deps() is True


class _FakeProcess:
    """Minimal stand-in for subprocess.Popen used to test wait_for_health."""

    def __init__(self, exit_code: int | None) -> None:
        self._exit_code = exit_code

    def poll(self) -> int | None:
        return self._exit_code


def test_wait_for_health_returns_false_immediately_if_process_already_exited():
    """A backend that crashed on startup must be reported immediately.

    This is the fix for "backend startup errors are swallowed": previously
    wait_for_health only polled /health and would wait out the full timeout
    even if the process had already died.
    """
    dead = _FakeProcess(exit_code=1)
    start = time.monotonic()
    result = run_desktop.wait_for_health(port=59999, process=dead, timeout=5.0)
    elapsed = time.monotonic() - start

    assert result is False
    # Should bail almost instantly, not wait out the 5s timeout.
    assert elapsed < 1.0


def test_wait_for_health_returns_false_on_timeout_with_live_but_unresponsive_process():
    # A process that never exits and never serves /health should time out
    # (using a genuinely free port so nothing responds).
    alive = _FakeProcess(exit_code=None)
    port = run_desktop.free_port()
    result = run_desktop.wait_for_health(port=port, process=alive, timeout=1.0)
    assert result is False


def test_check_node_does_not_raise():
    # Smoke test: check_node should not raise regardless of which npm shim
    # `shutil.which` resolves (relevant on Windows where npm is npm.cmd).
    result = run_desktop.check_node()
    assert result is None or isinstance(result, str)
