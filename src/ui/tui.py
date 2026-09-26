"""Minimal terminal UI. Deliberately plain (no curses) — reliability and agent
capability matter more than visual effects, per the spec."""
from __future__ import annotations

from src.agent.state import AgentState

WIDTH = 60


def _rule() -> str:
    return "-" * WIDTH


def print_header(repo: str, task: str) -> None:
    print(_rule())
    print("AUTONOMOUS CODING AGENT")
    print(_rule())
    print(f"Repository: {repo}")
    print(f"Task: {task}")
    print()


def make_activity_printer():
    """Returns a callback suitable for AgentLoop(on_activity=...) that prints
    each activity line live, prefixed like the spec's example TUI."""
    def _cb(line: str) -> None:
        print(f"> {line}")
    return _cb


def print_final(state: AgentState, verification_text: str) -> None:
    print()
    print(_rule())
    print("CHANGES:")
    if state.changed_files:
        for f in state.changed_files:
            print(f"  - {f}")
    else:
        print("  (none)")
    print()
    print("VERIFICATION:")
    for line in verification_text.splitlines():
        print(f"  {line}")
    print()
    print("FINAL:")
    if state.success:
        print("  \u2713 Task completed")
    else:
        print("  \u2717 Task not completed / not verified")
    print()
    print("SUMMARY:")
    print(_indent(state.final_summary))
    print(_rule())


def _indent(text: str, prefix: str = "  ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())
