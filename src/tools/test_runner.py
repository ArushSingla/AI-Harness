"""Detects and runs a project's test suite, returning structured pass/fail info."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .filesystem import Workspace, ToolResult

DEFAULT_TIMEOUT = 300


@dataclass
class TestResult:
    ok: bool
    command: str
    exit_code: int
    passed: Optional[int] = None
    failed: Optional[int] = None
    raw_output: str = ""
    summary: str = ""


def detect_test_command(workspace: Workspace, target: Optional[str] = None) -> Optional[str]:
    root = workspace.root
    if (root / "pytest.ini").exists() or (root / "conftest.py").exists() or list(root.glob("test_*.py")) or list(root.glob("tests")):
        base = "python -m pytest"
        return f"{base} -q {target}" if target else f"{base} -q"
    pkg = root / "package.json"
    if pkg.exists():
        try:
            import json
            data = json.loads(pkg.read_text())
            if "test" in data.get("scripts", {}):
                return "npm test --silent"
        except Exception:
            pass
    if (root / "go.mod").exists():
        return "go test ./..."
    if (root / "Cargo.toml").exists():
        return "cargo test"
    return None


_PYTEST_SUMMARY_RE = re.compile(
    r"(?:(?P<failed>\d+) failed,?\s*)?(?:(?P<passed>\d+) passed)?.*?in [\d.]+s"
)
_JEST_RE = re.compile(r"Tests:\s+(?:(?P<failed>\d+) failed,\s*)?(?:(?P<passed>\d+) passed,\s*)?(?P<total>\d+) total")


def _parse_summary(output: str) -> tuple[Optional[int], Optional[int]]:
    m = _PYTEST_SUMMARY_RE.search(output)
    if m and (m.group("passed") or m.group("failed")):
        p = int(m.group("passed")) if m.group("passed") else 0
        f = int(m.group("failed")) if m.group("failed") else 0
        return p, f
    m = _JEST_RE.search(output)
    if m:
        p = int(m.group("passed")) if m.group("passed") else 0
        f = int(m.group("failed")) if m.group("failed") else 0
        return p, f
    return None, None


def run_tests(workspace: Workspace, target: Optional[str] = None, timeout: int = DEFAULT_TIMEOUT) -> TestResult:
    command = detect_test_command(workspace, target)
    if not command:
        return TestResult(False, "", -1, raw_output="Could not detect a test framework for this project.")
    try:
        proc = subprocess.run(
            command, shell=True, cwd=str(workspace.root),
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return TestResult(False, command, -1, raw_output=f"Test run timed out after {timeout}s")

    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    passed, failed = _parse_summary(output)
    ok = proc.returncode == 0
    summary = f"{passed or 0} passed, {failed or 0} failed" if passed is not None or failed is not None else (
        "tests passed" if ok else "tests failed"
    )
    trimmed = output if len(output) < 8000 else output[:4000] + "\n...[truncated]...\n" + output[-4000:]
    return TestResult(ok, command, proc.returncode, passed, failed, trimmed, summary)


def to_tool_result(result: TestResult) -> ToolResult:
    tr = ToolResult(result.ok, f"$ {result.command}\n{result.raw_output}\nSummary: {result.summary}")
    tr.data = {"exit_code": result.exit_code, "passed": result.passed, "failed": result.failed}
    return tr
