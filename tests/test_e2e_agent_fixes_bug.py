"""End-to-end test: a scripted (mock) agent run against a small fake repository
with a deliberate bug. The script mimics what a real model would do: inspect,
search, read, patch with edit_file, then run tests and finish. This proves the
whole loop (state, tools, verification) works together without spending a real
API call."""
import json
import shutil
from pathlib import Path

from src.agent.loop import AgentLoop
from src.model.model_client import MockModelClient
from src.tools.filesystem import Workspace

TEMPLATE = Path(__file__).parent / "fake_repo_template"

OLD_LINE = '    domain = email.split("@")[1]  # raises if email is None or empty'
NEW_SNIPPET = (
    "    if not email:\n"
    "        return 400\n"
    "    domain = email.split(\"@\")[1]"
)


def _make_repo(tmp_path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(TEMPLATE, dest)
    return dest


def test_agent_fixes_missing_email_bug_end_to_end(tmp_path):
    repo = _make_repo(tmp_path)
    ws = Workspace(str(repo))

    script = [
        # 1. planner call
        json.dumps({"plan": [
            "Find the login function",
            "Understand why missing email causes a crash",
            "Fix validation",
            "Run tests",
            "Verify",
        ]}),
        # 2. search for the login route
        json.dumps({
            "thought": "Find where login is implemented",
            "action": "search_files",
            "arguments": {"query": "def login"},
        }),
        # 3. read the file to see the bug
        json.dumps({
            "thought": "Read auth.py to see the implementation",
            "action": "read_file",
            "arguments": {"path": "auth.py"},
        }),
        # 4. run tests first to confirm the failure
        json.dumps({
            "thought": "Confirm the bug via tests before changing anything",
            "action": "run_tests",
            "arguments": {},
        }),
        # 5. apply the fix
        json.dumps({
            "thought": "Add a missing-email guard before the crash-prone line",
            "action": "edit_file",
            "arguments": {
                "path": "auth.py",
                "old_str": OLD_LINE,
                "new_str": NEW_SNIPPET,
            },
        }),
        # 6. re-run tests
        json.dumps({
            "thought": "Re-run tests to verify the fix",
            "action": "run_tests",
            "arguments": {},
        }),
        # 7. finish
        json.dumps({
            "thought": "All tests pass now",
            "action": "finish",
            "arguments": {
                "success": True,
                "summary": "Added a guard for missing email in login(), returning 400 instead of crashing.",
            },
        }),
    ]
    model = MockModelClient(script)
    loop = AgentLoop(ws, model, "Fix the login API returning 500 when the email is missing.")
    result = loop.run()

    assert result.state.success is True
    assert "auth.py" in result.state.changed_files
    assert "400" in (repo / "auth.py").read_text()

    # Independent re-check, exactly like the harness's own final verification step.
    import subprocess
    proc = subprocess.run(["python3", "-m", "pytest", "-q"], cwd=repo, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "3 passed" in proc.stdout
