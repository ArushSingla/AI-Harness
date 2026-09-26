"""Read-only git introspection: status and diff. Never mutates history."""
from __future__ import annotations

import subprocess

from .filesystem import Workspace, ToolResult


def _run_git(workspace: Workspace, args: list[str]) -> ToolResult:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(workspace.root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return ToolResult(False, "git is not installed in this environment")
    except subprocess.TimeoutExpired:
        return ToolResult(False, "git command timed out")
    if proc.returncode != 0:
        return ToolResult(False, proc.stderr.strip() or f"git {' '.join(args)} failed")
    return ToolResult(True, proc.stdout).truncated()


def git_status(workspace: Workspace) -> ToolResult:
    return _run_git(workspace, ["status", "--porcelain=v1", "--branch"])


def git_diff(workspace: Workspace, path: str | None = None) -> ToolResult:
    args = ["diff", "--no-color"]
    if path:
        args += ["--", path]
    return _run_git(workspace, args)
