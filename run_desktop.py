#!/usr/bin/env python3
"""Development launcher for the LensTrace Studio desktop app.

Responsibilities:
  1. Validate Python dependencies are importable.
  2. Check that desktop Node dependencies are installed.
  3. Pick a free ephemeral loopback port.
  4. Generate a per-session token.
  5. Start the FastAPI backend (uvicorn) bound to 127.0.0.1:<port>.
  6. Wait for the backend /health endpoint to respond.
  7. Start the Electron/Vite desktop app, passing port + token via env.
  8. Shut the backend down cleanly when Electron exits or on Ctrl+C.

This launcher requires Python and Node.js. It never binds the backend to a
public interface and never prints the session token.
"""

from __future__ import annotations

import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DESKTOP_DIR = ROOT / "desktop"
HOST = "127.0.0.1"

# Terminal colours (no-op on plain terminals that ignore them).
_C = {"ok": "\033[92m", "warn": "\033[93m", "err": "\033[91m", "dim": "\033[90m", "end": "\033[0m"}


def _msg(kind: str, text: str) -> None:
    print(f"{_C.get(kind, '')}[{kind.upper()}]{_C['end']} {text}")


def check_python_deps() -> bool:
    """Confirm the backend's Python dependencies import."""
    required = ["fastapi", "uvicorn", "pydantic", "PIL", "piexif"]
    missing = []
    for mod in required:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        _msg("err", f"Missing Python packages: {', '.join(missing)}")
        _msg("dim", "Install them with:  pip install -r requirements.txt")
        return False
    _msg("ok", "Python dependencies present.")
    return True


def check_node() -> str | None:
    """Return the path to the npm executable, or None with guidance."""
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if npm is None:
        _msg("err", "Node.js / npm was not found on PATH.")
        _msg("dim", "Install Node.js 18+ from https://nodejs.org and re-run.")
        return None
    _msg("ok", "Node.js / npm found.")
    return npm


def check_node_modules(npm: str) -> bool:
    """Ensure desktop/node_modules exists; offer to install if not."""
    if (DESKTOP_DIR / "node_modules").is_dir():
        _msg("ok", "Desktop Node dependencies installed.")
        return True
    _msg("warn", "desktop/node_modules is missing. Installing (npm install)...")
    try:
        subprocess.run([npm, "install"], cwd=DESKTOP_DIR, check=True)
    except subprocess.CalledProcessError:
        _msg("err", "npm install failed. Run it manually in the desktop/ folder.")
        return False
    return True


def free_port() -> int:
    """Bind to port 0 on loopback to obtain a free ephemeral port, then release."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def start_backend(port: int, token: str) -> subprocess.Popen:
    """Start uvicorn with the backend app, bound to loopback only."""
    env = os.environ.copy()
    env["LENSTRACE_HOST"] = HOST
    env["LENSTRACE_PORT"] = str(port)
    env["LENSTRACE_SESSION_TOKEN"] = token
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        HOST,
        "--port",
        str(port),
        "--log-level",
        env.get("LOG_LEVEL", "info").lower(),
    ]
    _msg("dim", f"Using Python interpreter: {sys.executable}")
    _msg("dim", f"Starting backend on {HOST}:{port} (session token hidden).")
    # stdout/stderr are inherited (not captured) so uvicorn's own logs and any
    # startup traceback are printed directly, never swallowed.
    return subprocess.Popen(cmd, cwd=ROOT, env=env)


def wait_for_health(port: int, process: subprocess.Popen, timeout: float = 20.0) -> bool:
    """Poll /health until it responds, the backend process dies, or timeout elapses.

    Checking ``process.poll()`` on every iteration means a backend that fails
    to start (e.g. an import error) is reported immediately instead of only
    after the full timeout — its traceback appears above via inherited stdio.
    """
    url = f"http://{HOST}:{port}/health"
    deadline = time.time() + timeout
    attempts = 0
    while time.time() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            _msg(
                "err",
                f"Backend process exited early (code {exit_code}) before becoming healthy. "
                "See the traceback printed above.",
            )
            return False
        attempts += 1
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:  # noqa: S310 - loopback only
                if resp.status == 200:
                    _msg("ok", f"Backend is healthy after {attempts} attempt(s).")
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.4)
    _msg("err", f"Backend did not become healthy within {timeout:.0f}s ({attempts} attempts).")
    return False


def start_desktop(npm: str, port: int, token: str) -> subprocess.Popen:
    """Start the Electron + Vite dev environment."""
    env = os.environ.copy()
    env["LENSTRACE_BACKEND_PORT"] = str(port)
    env["LENSTRACE_BACKEND_HOST"] = HOST
    env["LENSTRACE_SESSION_TOKEN"] = token
    _msg(
        "dim",
        f"Starting desktop (npm run dev) with backend config host={HOST} port={port} "
        "token=<redacted>.",
    )
    return subprocess.Popen([npm, "run", "dev"], cwd=DESKTOP_DIR, env=env)


def main() -> int:
    print("LensTrace Studio — development launcher\n")

    if not check_python_deps():
        return 1
    npm = check_node()
    if npm is None:
        return 1
    if not check_node_modules(npm):
        return 1

    port = free_port()
    token = secrets.token_urlsafe(32)

    backend = start_backend(port, token)
    if not wait_for_health(port, backend):
        if backend.poll() is None:
            backend.terminate()
        return 1

    desktop = start_desktop(npm, port, token)

    def shutdown(*_args) -> None:
        _msg("dim", "Shutting down...")
        for proc in (desktop, backend):
            if proc and proc.poll() is None:
                proc.terminate()

    signal.signal(signal.SIGINT, lambda *_: shutdown())
    try:
        desktop.wait()
    except KeyboardInterrupt:
        pass
    finally:
        shutdown()
        # Give processes a moment, then hard-kill any stragglers.
        time.sleep(1.0)
        for proc in (desktop, backend):
            if proc and proc.poll() is None:
                proc.kill()
    _msg("ok", "Stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
