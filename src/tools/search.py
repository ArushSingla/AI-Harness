"""Simple in-repo text search, without shelling out to grep (keeps behavior portable/testable)."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List

from .filesystem import Workspace, ToolResult, DEFAULT_IGNORE_DIRS

MAX_MATCHES = 200
MAX_FILE_BYTES_TO_SCAN = 2_000_000  # skip huge/binary-ish files


def _looks_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
        return b"\0" in chunk
    except Exception:
        return True


def search_files(workspace: Workspace, pattern: str, rel_path: str = ".", regex: bool = False) -> ToolResult:
    try:
        base = workspace.resolve(rel_path)
    except Exception as e:
        return ToolResult(False, str(e))
    if not base.exists():
        return ToolResult(False, f"Path does not exist: {rel_path}")

    matcher = re.compile(pattern) if regex else None
    results: List[str] = []

    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_IGNORE_DIRS and not d.startswith(".")]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            try:
                if fpath.stat().st_size > MAX_FILE_BYTES_TO_SCAN or _looks_binary(fpath):
                    continue
                with open(fpath, "r", errors="ignore") as f:
                    for i, line in enumerate(f, start=1):
                        hit = matcher.search(line) if matcher else (pattern in line)
                        if hit:
                            rel = workspace.rel(fpath)
                            results.append(f"{rel}:{i}: {line.strip()[:200]}")
                            if len(results) >= MAX_MATCHES:
                                results.append(f"...[truncated, more than {MAX_MATCHES} matches]")
                                return ToolResult(True, "\n".join(results))
            except (OSError, UnicodeDecodeError):
                continue

    if not results:
        return ToolResult(True, f"No matches for '{pattern}' under {rel_path}")
    return ToolResult(True, "\n".join(results))
