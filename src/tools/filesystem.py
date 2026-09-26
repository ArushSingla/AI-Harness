"""Filesystem tools: list, read, write, edit, delete — all sandboxed to a workspace root."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

MAX_LIST_ENTRIES = 300
MAX_READ_CHARS = 20_000
DEFAULT_IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".pytest_cache", ".mypy_cache", ".idea", ".vscode",
}


class PathSafetyError(Exception):
    """Raised when a tool tries to touch a path outside the workspace."""


@dataclass
class ToolResult:
    ok: bool
    output: str
    data: Optional[dict] = None

    def truncated(self, limit: int = MAX_READ_CHARS) -> "ToolResult":
        if len(self.output) > limit:
            head = self.output[: limit // 2]
            tail = self.output[-limit // 2:]
            omitted = len(self.output) - limit
            self.output = f"{head}\n...[truncated {omitted} chars]...\n{tail}"
        return self


class Workspace:
    """Resolves and guards all filesystem access to stay inside `root`."""

    def __init__(self, root: str):
        self.root = Path(root).resolve()
        if not self.root.exists():
            raise FileNotFoundError(f"Workspace root does not exist: {root}")

    def resolve(self, rel_path: str) -> Path:
        # Reject absolute paths that try to escape, and any ../ traversal.
        candidate = (self.root / rel_path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            raise PathSafetyError(
                f"Path '{rel_path}' resolves outside the workspace ({self.root})"
            )
        return candidate

    def rel(self, abs_path: Path) -> str:
        try:
            return str(abs_path.relative_to(self.root))
        except ValueError:
            return str(abs_path)

    # ---- tools ----

    def list_files(self, rel_path: str = ".", max_depth: int = 2) -> ToolResult:
        try:
            base = self.resolve(rel_path)
        except PathSafetyError as e:
            return ToolResult(False, str(e))
        if not base.exists():
            return ToolResult(False, f"Path does not exist: {rel_path}")

        entries: List[str] = []
        base_depth = len(base.parts)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in DEFAULT_IGNORE_DIRS and not d.startswith(".")]
            depth = len(Path(dirpath).parts) - base_depth
            if depth > max_depth:
                dirnames[:] = []
                continue
            rel_dir = self.rel(Path(dirpath))
            if rel_dir != ".":
                entries.append(f"{rel_dir}/")
            for f in sorted(filenames):
                entries.append(str(Path(rel_dir, f)) if rel_dir != "." else f)
            if len(entries) > MAX_LIST_ENTRIES:
                entries = entries[:MAX_LIST_ENTRIES]
                entries.append(f"...[truncated, more than {MAX_LIST_ENTRIES} entries]")
                break
        return ToolResult(True, "\n".join(entries) if entries else "(empty)")

    def read_file(self, rel_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> ToolResult:
        try:
            path = self.resolve(rel_path)
        except PathSafetyError as e:
            return ToolResult(False, str(e))
        if not path.exists() or not path.is_file():
            return ToolResult(False, f"File not found: {rel_path}")
        try:
            text = path.read_text(errors="replace")
        except Exception as e:  # pragma: no cover - defensive
            return ToolResult(False, f"Could not read {rel_path}: {e}")

        if start_line is not None or end_line is not None:
            lines = text.splitlines()
            s = max((start_line or 1) - 1, 0)
            e = end_line if end_line is not None else len(lines)
            snippet = "\n".join(lines[s:e])
            return ToolResult(True, snippet).truncated()
        return ToolResult(True, text).truncated()

    def write_file(self, rel_path: str, content: str) -> ToolResult:
        try:
            path = self.resolve(rel_path)
        except PathSafetyError as e:
            return ToolResult(False, str(e))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return ToolResult(True, f"Wrote {len(content)} chars to {rel_path}")

    def edit_file(self, rel_path: str, old_str: str, new_str: str) -> ToolResult:
        try:
            path = self.resolve(rel_path)
        except PathSafetyError as e:
            return ToolResult(False, str(e))
        if not path.exists():
            return ToolResult(False, f"File not found: {rel_path}")
        text = path.read_text()
        count = text.count(old_str)
        if count == 0:
            return ToolResult(False, f"old_str not found in {rel_path}")
        if count > 1:
            return ToolResult(False, f"old_str matches {count} times in {rel_path}; must be unique")
        path.write_text(text.replace(old_str, new_str, 1))
        return ToolResult(True, f"Edited {rel_path}")

    def delete_file(self, rel_path: str) -> ToolResult:
        try:
            path = self.resolve(rel_path)
        except PathSafetyError as e:
            return ToolResult(False, str(e))
        if not path.exists():
            return ToolResult(False, f"File not found: {rel_path}")
        if path.is_dir():
            return ToolResult(False, f"Refusing to delete a directory via delete_file: {rel_path}")
        path.unlink()
        return ToolResult(True, f"Deleted {rel_path}")
