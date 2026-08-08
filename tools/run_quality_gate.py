#!/usr/bin/env python3
"""Run the complete, repository-local OmniOps Video Studio quality gate."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def command_check(name: str, command: list[str]) -> dict:
    completed = run(command)
    output = completed.stdout.strip()
    return {
        "name": name,
        "ok": completed.returncode == 0,
        "exitCode": completed.returncode,
        "outputTail": "\n".join(output.splitlines()[-20:]),
    }


def boundary_check() -> dict:
    completed = run([sys.executable, str(ROOT / "tools/verify_public_boundary.py")])
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {"ok": False, "violations": ["invalid scanner output"]}
    return {
        "name": "publicBoundaryAndSecretScan",
        "ok": completed.returncode == 0 and payload.get("ok") is True,
        "exitCode": completed.returncode,
        "files": payload.get("files", 0),
        "violations": payload.get("violations", []),
    }


def python_syntax_check() -> dict:
    failures: list[dict[str, str]] = []
    checked = 0
    for parent in (ROOT / "backend", ROOT / "tests", ROOT / "tools"):
        for path in sorted(parent.rglob("*.py")):
            checked += 1
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, UnicodeError, SyntaxError) as exc:
                failures.append(
                    {
                        "path": str(path.relative_to(ROOT)),
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
    return {
        "name": "pythonSyntax",
        "ok": not failures,
        "checked": checked,
        "failures": failures,
    }


def cargo_metadata_check() -> dict:
    completed = run(
        [
            "cargo",
            "metadata",
            "--manifest-path",
            str(ROOT / "src-tauri" / "Cargo.toml"),
            "--no-deps",
            "--format-version",
            "1",
        ]
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {}
    packages = len(payload.get("packages", []))
    members = len(payload.get("workspace_members", []))
    return {
        "name": "rustTauriMetadata",
        "ok": completed.returncode == 0 and packages == 1 and members == 1,
        "exitCode": completed.returncode,
        "packages": packages,
        "workspaceMembers": members,
        "outputTail": "\n".join(completed.stdout.strip().splitlines()[-10:])
        if completed.returncode
        else "",
    }


def regression_test_check() -> dict:
    completed = run(
        [sys.executable, str(ROOT / "tests" / "test_omniops_video_studio.py")]
    )
    match = re.search(r"Ran\s+(\d+)\s+tests?", completed.stdout)
    tests = int(match.group(1)) if match else 0
    return {
        "name": "videoStudioRegression",
        "ok": completed.returncode == 0 and tests == 27 and "OK" in completed.stdout,
        "exitCode": completed.returncode,
        "tests": tests,
        "outputTail": "\n".join(completed.stdout.strip().splitlines()[-10:]),
    }


def evaluate() -> dict:
    checks = [
        boundary_check(),
        python_syntax_check(),
        command_check("npmCleanInstall", ["npm", "ci", "--no-audit", "--no-fund"]),
        command_check("typescriptViteBuild", ["npm", "run", "build"]),
        cargo_metadata_check(),
        regression_test_check(),
    ]
    failed = [check["name"] for check in checks if not check.get("ok")]
    return {
        "schema": "omniops.video_studio_quality_gate.v1",
        "status": "PASS" if not failed else "FAIL",
        "repository": str(ROOT),
        "checks": checks,
        "failedChecks": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args()
    result = evaluate()
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["status"])
        for check in result["checks"]:
            details = ""
            if "tests" in check:
                details = f" ({check['tests']}/27)"
            elif "checked" in check:
                details = f" ({check['checked']})"
            print(f"- {check['name']}: {'PASS' if check.get('ok') else 'FAIL'}{details}")
        if result["failedChecks"]:
            print("failedChecks=" + ",".join(result["failedChecks"]))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
