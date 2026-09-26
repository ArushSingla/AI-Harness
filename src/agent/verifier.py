"""Independently verifies agent-claimed completion before reporting success."""
from __future__ import annotations

from dataclasses import dataclass

from src.tools.filesystem import Workspace
from src.tools.git_tools import git_diff
from src.tools.test_runner import run_tests, TestResult


@dataclass
class VerificationReport:
    tests_ran: bool
    tests_passed: bool
    test_result: TestResult | None
    has_diff: bool
    diff_excerpt: str

    def to_text(self) -> str:
        lines = []
        if self.tests_ran:
            status = "PASSED" if self.tests_passed else "FAILED"
            lines.append(f"Tests: {status} ({self.test_result.summary if self.test_result else ''})")
        else:
            lines.append("Tests: not run / no test framework detected")
        lines.append(f"Uncommitted diff present: {'yes' if self.has_diff else 'no'}")
        return "\n".join(lines)


def verify(workspace: Workspace) -> VerificationReport:
    result = run_tests(workspace)
    tests_ran = result.command != ""
    diff = git_diff(workspace)
    has_diff = bool(diff.output.strip())
    return VerificationReport(
        tests_ran=tests_ran,
        tests_passed=result.ok if tests_ran else False,
        test_result=result if tests_ran else None,
        has_diff=has_diff,
        diff_excerpt=diff.output[:2000],
    )
