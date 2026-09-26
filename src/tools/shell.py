"""Runs shell commands scoped to the workspace, blocking obviously destructive commands."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

from .filesystem import Workspace, ToolResult

DEFAULT_TIMEOUT = 120

# Patterns that are blocked outright, no matter what. These are conservative substring/regex
# checks intended to stop catastrophic mistakes, not a full shell-security sandbox.
DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/(?!\S)",          # rm -rf /
    r"rm\s+-rf\s+/\*",              # rm -rf /*
    r"rm\s+-rf\s+~",                # rm -rf ~
    r"rm\s+-rf\s+\.\.",             # rm -rf out of workspace via ..
    r"\bmkfs\b",
    r"\bdd\s+.*of=/dev/",
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&?\s*\}\s*;\s*:",  # fork bomb
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-[a-zA-Z]*f",
    r"\bgit\s+push\s+.*--force\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bchmod\s+-R\s+000\b",
    r">\s*/dev/sda",
    r"\bcurl\b.*\|\s*sh\b",
    r"\bwget\b.*\|\s*sh\b",
    r"\bcat\s+.*\.env\b",           # discourage secret exfiltration
    r"\bprintenv\b",
    r"\benv\b\s*$",
]

_COMPILED = [re.compile(p) for p in DANGEROUS_PATTERNS]


def is_dangerous(command: str) -> str | None:
    for pat in _COMPILED:
        if pat.search(command):
            return pat.pattern
    return None


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    blocked: bool = False
    block_reason: str = ""


def run_command(workspace: Workspace, command: str, timeout: int = DEFAULT_TIMEOUT, allow_dangerous: bool = False) -> ToolResult:
    reason = is_dangerous(command)
    if reason and not allow_dangerous:
        return ToolResult(
            False,
            f"BLOCKED: command matches a destructive pattern ({reason}). "
            f"Refusing to run '{command}'. If this is truly required, a human must run it manually.",
        )
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(workspace.root),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(False, f"Command timed out after {timeout}s: {command}")
    except Exception as e:  # pragma: no cover - defensive
        return ToolResult(False, f"Failed to run command: {e}")

    out = (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
    ok = proc.returncode == 0
    result = ToolResult(ok, out or f"(no output, exit code {proc.returncode})")
    result.data = {"exit_code": proc.returncode}
    return result.truncated()
