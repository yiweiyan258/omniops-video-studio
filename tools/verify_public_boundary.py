#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
BANNED_TOP = {"data", "reports", "dashboard", "runtime-packages", "external", "prompt-assets"}
BANNED_SUFFIX = {".pem", ".key", ".sqlite", ".sqlite3", ".db", ".mp4", ".mov", ".wav", ".mp3"}
PATTERNS = [
    re.compile(r"xai-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"(?:gh[pousr]_|github_pat_)[0-9A-Za-z_]{20,}"),
    re.compile(r"sk-[0-9A-Za-z_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]


violations: list[dict] = []
files = 0
for dp, dns, fns in os.walk(ROOT, followlinks=False):
    dns[:] = [d for d in dns if d not in {".git", "node_modules", "target", "dist"}]
    for name in fns:
        p = Path(dp) / name
        if p.resolve() == SELF:
            continue
        rel = p.relative_to(ROOT)
        files += 1
        if rel.parts and rel.parts[0] in BANNED_TOP:
            violations.append({"type": "banned_top_level", "path": str(rel)})
            continue
        if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
            violations.append({"type": "live_environment_file", "path": str(rel)})
            continue
        if p.suffix.lower() in BANNED_SUFFIX:
            violations.append({"type": "banned_suffix", "path": str(rel)})
            continue
        if p.is_symlink():
            violations.append({"type": "symlink_not_allowed", "path": str(rel)})
            continue
        if p.stat().st_size > 20 * 1024 * 1024:
            violations.append({"type": "file_over_20_mib", "path": str(rel)})
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if any(pattern.search(text) for pattern in PATTERNS):
            violations.append({"type": "high_confidence_secret", "path": str(rel)})

result = {"ok": not violations, "root": str(ROOT), "files": files, "violations": violations}
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result["ok"] else 1)

