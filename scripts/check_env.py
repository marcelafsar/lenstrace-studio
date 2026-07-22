#!/usr/bin/env python3
"""LensTrace Studio environment / configuration checker.

Usage:
    python scripts/check_env.py
    python scripts/check_env.py --service all|telegram|discord|delivery
    python scripts/check_env.py --json
    python scripts/check_env.py --strict
    python scripts/check_env.py --connectivity

Exit codes:
    0  all required checks passed
    1  a required check failed
    2  configuration is invalid
    3  unexpected checker error

Secret values are never printed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services.env_check_service import CheckStatus, run_checks  # noqa: E402

_COLOR = {
    CheckStatus.PASS: "\033[92m",
    CheckStatus.WARN: "\033[93m",
    CheckStatus.FAIL: "\033[91m",
}
_RESET = "\033[0m"


def _print_human(report, use_color: bool) -> None:
    for r in report.results:
        tag = r.status.value
        if use_color:
            tag = f"{_COLOR[r.status]}{tag}{_RESET}"
        detail = f" - {r.detail}" if r.detail else ""
        print(f"[{tag}] {r.name}{detail}")
    print(f"\n{report.passed} passed, {report.warned} warning(s), {report.failed} failed.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LensTrace environment checker")
    parser.add_argument(
        "--service",
        default="all",
        choices=["all", "telegram", "discord", "delivery", "geocoding"],
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output.")
    parser.add_argument(
        "--strict", action="store_true", help="Enabled integrations must be fully configured."
    )
    parser.add_argument(
        "--connectivity", action="store_true", help="Also validate bot tokens over the network."
    )
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colours.")
    args = parser.parse_args(argv)

    try:
        report = run_checks(
            service=args.service, strict=args.strict, connectivity=args.connectivity
        )
    except Exception as exc:  # noqa: BLE001 - unexpected checker error → exit 3
        if args.json:
            print(json.dumps({"error": type(exc).__name__}))
        else:
            print(f"[FAIL] Checker error: {type(exc).__name__}", file=sys.stderr)
        return 3

    if args.json:
        # JSON output is pure data with no ANSI codes.
        print(report.model_dump_json(indent=2))
    else:
        _print_human(report, use_color=not args.no_color)

    if report.config_invalid:
        return 2
    if report.failed > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
