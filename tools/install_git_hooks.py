#!/usr/bin/env python3
"""Enable the versioned Video Studio quality-gate hooks for this checkout."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".githooks" / "pre-push"


def main() -> int:
    if not HOOK.is_file():
        raise SystemExit(f"missing hook: {HOOK}")
    HOOK.chmod(HOOK.stat().st_mode | 0o111)
    subprocess.run(
        ["git", "config", "core.hooksPath", ".githooks"],
        cwd=ROOT,
        check=True,
    )
    configured = subprocess.check_output(
        ["git", "config", "--get", "core.hooksPath"],
        cwd=ROOT,
        text=True,
    ).strip()
    if configured != ".githooks":
        raise SystemExit(f"unexpected hooks path: {configured}")
    print("PASS: core.hooksPath=.githooks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
