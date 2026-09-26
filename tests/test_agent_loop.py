import json

import pytest

from src.agent.loop import AgentLoop, _parse_action, MAX_RETRIES
from src.model.model_client import MockModelClient
from src.tools.filesystem import Workspace


def test_parse_action_valid_json():
    raw = '{"thought": "t", "action": "list_files", "arguments": {"path": "."}}'
    obj = _parse_action(raw)
    assert obj["action"] == "list_files"


def test_parse_action_strips_surrounding_prose():
    raw = 'Sure, here it is:\n{"action": "list_files", "arguments": {}}\nDone.'
    obj = _parse_action(raw)
    assert obj["action"] == "list_files"


def test_parse_action_rejects_missing_action():
    with pytest.raises(ValueError):
        _parse_action('{"thought": "t"}')


def test_parse_action_rejects_non_json():
    with pytest.raises(ValueError):
        _parse_action("not json at all")


def test_agent_loop_finish_action_ends_run(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    ws = Workspace(str(tmp_path))
    script = [
        json.dumps({"plan": ["step1"]}),  # planner call
        json.dumps({"thought": "done", "action": "finish", "arguments": {"success": True, "summary": "did it"}}),
    ]
    model = MockModelClient(script)
    loop = AgentLoop(ws, model, "trivial task")
    result = loop.run()
    assert result.state.finished
    assert result.state.success is True
    assert result.state.final_summary == "did it"


def test_agent_loop_recovers_from_bad_action_then_finishes(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    ws = Workspace(str(tmp_path))
    script = [
        json.dumps({"plan": ["step1"]}),
        json.dumps({"thought": "list", "action": "list_files", "arguments": {"path": "."}}),
        json.dumps({"thought": "done", "action": "finish", "arguments": {"success": True, "summary": "ok"}}),
    ]
    model = MockModelClient(script)
    loop = AgentLoop(ws, model, "trivial task")
    result = loop.run()
    assert result.state.success is True
    assert any("list_files" in line for line in result.state.activity_log)


def test_agent_loop_gives_up_after_max_consecutive_failures(tmp_path):
    ws = Workspace(str(tmp_path))
    # Planner call, then repeated malformed responses (no JSON at all).
    script = [json.dumps({"plan": ["step1"]})] + ["not json"] * (MAX_RETRIES + 2)
    model = MockModelClient(script)
    loop = AgentLoop(ws, model, "trivial task")
    result = loop.run()
    assert result.state.finished
    assert result.state.success is False
    assert "malformed" in result.state.final_summary.lower() or "failed" in result.state.final_summary.lower()


def test_agent_loop_downgrades_success_if_tests_actually_fail(tmp_path):
    (tmp_path / "test_x.py").write_text("def test_fails():\n    assert False\n")
    ws = Workspace(str(tmp_path))
    script = [
        json.dumps({"plan": ["step1"]}),
        json.dumps({"thought": "claim done", "action": "finish", "arguments": {"success": True, "summary": "done, trust me"}}),
    ]
    model = MockModelClient(script)
    loop = AgentLoop(ws, model, "make tests pass")
    result = loop.run()
    # The agent claimed success, but independent verification re-runs tests and finds a failure.
    assert result.state.success is False
    assert "NOT VERIFIED" in result.state.final_summary
