"""The autonomous agent loop.

while task not finished:
    understand current state -> build compact prompt from AgentState
    decide next action        -> ask the model for a single JSON action
    call tool                 -> execute it against the sandboxed workspace
    observe result             -> capture tool output
    update context             -> fold the result into AgentState
    (loop)

Includes retry limits so a stuck agent terminates with a clear report instead
of looping forever, and re-verifies before claiming success.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Optional

from src.model.model_client import ModelClient, ModelError
from src.tools.filesystem import Workspace, ToolResult
from src.tools import search as search_tool
from src.tools import shell as shell_tool
from src.tools import git_tools
from src.tools.test_runner import run_tests, to_tool_result
from src.repository.analyzer import analyze_repository

from .state import AgentState
from .context import SYSTEM_PROMPT, build_messages
from .planner import make_plan
from .verifier import verify

MAX_ITERATIONS = 40
MAX_RETRIES = 5  # consecutive failed/erroring actions before giving up


@dataclass
class RunResult:
    state: AgentState
    verification_text: str


ActivityCallback = Optional[Callable[[str], None]]


class AgentLoop:
    def __init__(self, workspace: Workspace, model: ModelClient, task: str, on_activity: ActivityCallback = None):
        self.workspace = workspace
        self.model = model
        self.state = AgentState(task=task)
        self.on_activity = on_activity or (lambda _line: None)
        self._consecutive_failures = 0
        self._seen_action_signatures: dict[str, int] = {}

    def _emit(self, line: str) -> None:
        self.state.log(line)
        self.on_activity(line)

    def run(self) -> RunResult:
        # 1. Repository understanding, up front, once.
        self._emit("Inspecting repository...")
        try:
            summary = analyze_repository(self.workspace)
            self.state.repo_summary = summary.to_text()
            self._emit("Repository inspected.")
        except Exception as e:
            self._emit(f"Repository inspection failed ({e}); proceeding without a summary.")
            self.state.repo_summary = "(repository inspection failed)"

        # 2. Initial plan.
        self._emit("Creating plan...")
        try:
            self.state.plan = make_plan(self.model, self.state.task, self.state.repo_summary)
        except ModelError as e:
            self._emit(f"Planning failed ({e}); proceeding with a generic plan.")
            self.state.plan = ["Inspect code", "Implement change", "Run tests", "Verify"]
        for step in self.state.plan:
            self._emit(f"Plan step: {step}")

        # 3. Main loop.
        last_observation: Optional[str] = "Repository inspected and plan created."
        for iteration in range(1, MAX_ITERATIONS + 1):
            if self.state.finished:
                break
            try:
                action_obj = self._decide_next_action(last_observation)
            except ModelError as e:
                self._register_failure(f"Model call failed: {e}")
                last_observation = f"ERROR calling model: {e}"
                if self._consecutive_failures >= MAX_RETRIES:
                    self._give_up("Model repeatedly failed to respond.")
                    break
                continue
            except ValueError as e:
                self._register_failure(f"Malformed model response: {e}")
                last_observation = f"Your last response could not be parsed as JSON: {e}. Respond with ONLY a JSON object."
                if self._consecutive_failures >= MAX_RETRIES:
                    self._give_up("Model repeatedly returned malformed responses.")
                    break
                continue

            thought = action_obj.get("thought", "")
            action = action_obj.get("action", "")
            args = action_obj.get("arguments", {}) or {}
            if thought:
                self._emit(f"({action}) {thought}")

            if action == "finish":
                self._handle_finish(args)
                break

            result = self._execute_tool(action, args)
            last_observation = self._render_observation(action, result)

            if result.ok:
                self._consecutive_failures = 0
            else:
                self._register_failure(f"{action} failed: {result.output[:200]}")
                self.state.current_error = result.output[:500]
                if self._consecutive_failures >= MAX_RETRIES:
                    self._give_up(f"Exceeded {MAX_RETRIES} consecutive tool failures.")
                    break
        else:
            self._give_up(f"Exceeded {MAX_ITERATIONS} iterations without finishing.")

        # 4. Independent, final verification — never trust the model's own claim alone.
        self._emit("Running final verification...")
        report = verify(self.workspace)
        self._emit(report.to_text())
        if self.state.success and not report.tests_ran:
            # No test suite to confirm with — keep the claim but flag it clearly downstream.
            pass
        elif self.state.success and report.tests_ran and not report.tests_passed:
            self.state.success = False
            self.state.final_summary += "\n\nNOTE: Final verification re-ran tests and they did NOT pass; downgraded to NOT VERIFIED."
        return RunResult(state=self.state, verification_text=report.to_text())

    # ---- internals ----

    def _decide_next_action(self, last_observation: Optional[str]) -> dict:
        messages = build_messages(self.state, last_observation)
        raw = self.model.complete(SYSTEM_PROMPT, messages)
        return _parse_action(raw)

    def _register_failure(self, msg: str) -> None:
        self._consecutive_failures += 1
        self.state.retries += 1
        self._emit(f"[error] {msg}")

    def _give_up(self, reason: str) -> None:
        self.state.finished = True
        self.state.success = False
        self.state.final_summary = (
            f"Could not complete the task automatically.\nReason: {reason}\n"
            f"Attempted plan: {self.state.plan}\n"
            f"Changed files so far: {self.state.changed_files}\n"
            f"Last error: {self.state.current_error}"
        )
        self._emit(f"Giving up: {reason}")

    def _handle_finish(self, args: dict) -> None:
        self.state.finished = True
        self.state.success = bool(args.get("success", False))
        self.state.final_summary = str(args.get("summary", "")) or "(no summary provided)"
        self._emit(f"Agent reported finish: success={self.state.success}")

    def _execute_tool(self, action: str, args: dict) -> ToolResult:
        try:
            if action == "inspect_project":
                summary = analyze_repository(self.workspace)
                self.state.repo_summary = summary.to_text()
                return ToolResult(True, summary.to_text())
            if action == "list_files":
                return self.workspace.list_files(args.get("path", "."))
            if action == "search_files":
                return search_tool.search_files(self.workspace, args["query"], args.get("path", "."))
            if action == "read_file":
                path = args["path"]
                if path not in self.state.important_files:
                    self.state.important_files.append(path)
                return self.workspace.read_file(path, args.get("start_line"), args.get("end_line"))
            if action == "write_file":
                self.state.note_change(args["path"])
                return self.workspace.write_file(args["path"], args.get("content", ""))
            if action == "edit_file":
                self.state.note_change(args["path"])
                return self.workspace.edit_file(args["path"], args["old_str"], args["new_str"])
            if action == "delete_file":
                self.state.note_change(args["path"])
                return self.workspace.delete_file(args["path"])
            if action == "run_command":
                return shell_tool.run_command(self.workspace, args["command"])
            if action == "run_tests":
                result = run_tests(self.workspace, args.get("target"))
                self.state.tests_run.append(result.command)
                self.state.test_status = "passed" if result.ok else f"failed ({result.summary})"
                if result.ok:
                    self.state.current_error = None
                return to_tool_result(result)
            if action == "git_diff":
                return git_tools.git_diff(self.workspace, args.get("path"))
            if action == "git_status":
                return git_tools.git_status(self.workspace)
            return ToolResult(False, f"Unknown action: {action}")
        except KeyError as e:
            return ToolResult(False, f"Missing required argument {e} for action '{action}'")
        except Exception as e:  # pragma: no cover - defensive catch-all so the loop never crashes
            return ToolResult(False, f"Tool '{action}' raised an unexpected error: {e}")

    @staticmethod
    def _render_observation(action: str, result: ToolResult) -> str:
        status = "OK" if result.ok else "ERROR"
        return f"[{action}] {status}\n{result.output}"


def _parse_action(raw: str) -> dict:
    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object found in response: {raw[:200]!r}")
    snippet = raw[start:end + 1]
    try:
        obj = json.loads(snippet)
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON: {e}") from e
    if "action" not in obj:
        raise ValueError("response JSON missing required 'action' field")
    return obj
