"""Keeps the model's input bounded: we never replay full conversation history.
Instead each turn sends the compact AgentState plus the single most-recent tool
observation. This avoids unbounded growth and unnecessary token usage."""
from __future__ import annotations

from .state import AgentState

TOOLS_DESCRIPTION = """\
Available tools (call exactly one per turn):

- inspect_project(): re-summarize the repository (rarely needed after the first call).
- list_files(path="."): list files/directories under path (depth-limited).
- search_files(query, path="."): search for a string across the repo, returns file:line matches.
- read_file(path, start_line=None, end_line=None): read a file, optionally a line range.
- write_file(path, content): create or fully overwrite a file.
- edit_file(path, old_str, new_str): replace one unique occurrence of old_str with new_str.
- delete_file(path): delete a file.
- run_command(command): run a shell command in the repo (destructive commands are blocked).
- run_tests(target=None): run the project's test suite (or a targeted subset).
- git_diff(path=None): show uncommitted changes.
- git_status(): show repository status.
- finish(success, summary): call this ONLY when the task is complete (or unrecoverable),
  with `success` true/false and a `summary` describing what was done/verified/blocked.

Respond with ONLY a single JSON object, no prose outside it, no markdown fences:
{"thought": "<brief internal reasoning, 1-3 sentences>",
 "action": "<tool name>",
 "arguments": {...}}
"""

SYSTEM_PROMPT = """You are an autonomous coding agent. You are given a software-engineering
task and a workspace containing a git repository. You must use the provided tools to
inspect the repository, make the necessary changes, run tests, and verify your work.

Rules:
- Use tools; never claim a change was made without actually calling write_file/edit_file.
- Never assume a fix works — run tests to check.
- Prefer targeted reads/searches over reading entire files or the whole repo.
- If tests fail, diagnose the failure from the output before trying again.
- Call `finish` only once the task is truly done and verified, or you are certain
  you cannot proceed further (explain why in the summary).
- Keep `thought` short. Do not reveal extended chain-of-thought.
""" + "\n" + TOOLS_DESCRIPTION


def build_messages(state: AgentState, last_observation: str | None) -> list[dict]:
    """One user message containing the compact state + the latest tool result.
    We deliberately do NOT resend the full history — the state block already
    carries everything durable (plan, changed files, test status, recent log)."""
    parts = [state.to_prompt_block()]
    if last_observation is not None:
        parts.append(f"LATEST TOOL OBSERVATION:\n{last_observation}")
    parts.append("What is the next action? Respond with the JSON object only.")
    return [{"role": "user", "content": "\n\n".join(parts)}]
