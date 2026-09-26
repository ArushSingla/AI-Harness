"""Compact, serializable agent state — this is what gets fed back to the model each turn
instead of full conversation history, keeping context usage bounded."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

MAX_ACTIVITY_LOG = 25
MAX_LOG_LINE = 300


@dataclass
class AgentState:
    task: str
    repo_summary: str = ""
    plan: List[str] = field(default_factory=list)
    important_files: List[str] = field(default_factory=list)
    changed_files: List[str] = field(default_factory=list)
    tests_run: List[str] = field(default_factory=list)
    test_status: str = "not run"
    current_error: Optional[str] = None
    next_action: str = ""
    activity_log: List[str] = field(default_factory=list)
    retries: int = 0
    finished: bool = False
    success: Optional[bool] = None
    final_summary: str = ""

    def log(self, line: str) -> None:
        if len(line) > MAX_LOG_LINE:
            line = line[:MAX_LOG_LINE] + "...[truncated]"
        self.activity_log.append(line)
        if len(self.activity_log) > MAX_ACTIVITY_LOG:
            # Collapse older entries into a single summary line to bound context growth.
            dropped = len(self.activity_log) - MAX_ACTIVITY_LOG
            self.activity_log = [f"[...{dropped} earlier steps omitted...]"] + self.activity_log[-MAX_ACTIVITY_LOG:]

    def note_change(self, path: str) -> None:
        if path not in self.changed_files:
            self.changed_files.append(path)

    def to_prompt_block(self) -> str:
        """Render the compact state block sent to the model each turn."""
        lines = [
            f"TASK: {self.task}",
            f"PLAN:\n" + ("\n".join(f"  {i+1}. {s}" for i, s in enumerate(self.plan)) if self.plan else "  (not yet created)"),
            f"REPOSITORY SUMMARY:\n{self.repo_summary or '(not yet inspected)'}",
            f"IMPORTANT FILES: {', '.join(self.important_files) or 'none yet'}",
            f"CHANGED FILES: {', '.join(self.changed_files) or 'none yet'}",
            f"TEST STATUS: {self.test_status}",
            f"CURRENT ERROR: {self.current_error or 'none'}",
            f"RECENT ACTIVITY:\n" + ("\n".join(f"  > {a}" for a in self.activity_log[-10:]) or "  (none yet)"),
        ]
        return "\n\n".join(lines)
