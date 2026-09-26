"""Produces a short initial plan. The plan is stored in AgentState and can be
revised by the agent loop later (e.g. via a `revise_plan` action) as new
information about the repository comes in."""
from __future__ import annotations

import json

from src.model.model_client import ModelClient

PLAN_SYSTEM_PROMPT = """You are planning how an autonomous coding agent will approach a task.
Given the task and a repository summary, produce a short ordered plan (3-7 steps).
Respond with ONLY a JSON object: {"plan": ["step 1", "step 2", ...]}
No prose outside the JSON."""


def make_plan(model: ModelClient, task: str, repo_summary: str) -> list[str]:
    messages = [{
        "role": "user",
        "content": f"TASK: {task}\n\nREPOSITORY SUMMARY:\n{repo_summary}\n\nProduce the plan.",
    }]
    raw = model.complete(PLAN_SYSTEM_PROMPT, messages)
    try:
        data = json.loads(_extract_json(raw))
        plan = data.get("plan", [])
        if isinstance(plan, list) and plan:
            return [str(s) for s in plan]
    except Exception:
        pass
    # Fallback: a generic, still-useful plan rather than a hard failure.
    return [
        "Inspect the repository structure and relevant source files.",
        "Search for code related to the task.",
        "Implement the required change.",
        "Run the test suite.",
        "Debug any failures and re-run tests.",
        "Verify the requested behavior is complete.",
    ]


def _extract_json(text: str) -> str:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response")
    return text[start:end + 1]
