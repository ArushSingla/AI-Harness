from src.agent.state import AgentState, MAX_ACTIVITY_LOG
from src.agent.context import build_messages


def test_activity_log_truncates():
    state = AgentState(task="demo")
    for i in range(MAX_ACTIVITY_LOG + 10):
        state.log(f"step {i}")
    assert len(state.activity_log) <= MAX_ACTIVITY_LOG + 1
    assert "omitted" in state.activity_log[0]


def test_note_change_is_deduped():
    state = AgentState(task="demo")
    state.note_change("a.py")
    state.note_change("a.py")
    state.note_change("b.py")
    assert state.changed_files == ["a.py", "b.py"]


def test_to_prompt_block_contains_key_sections():
    state = AgentState(task="fix bug")
    state.plan = ["do x", "do y"]
    text = state.to_prompt_block()
    assert "TASK: fix bug" in text
    assert "do x" in text
    assert "REPOSITORY SUMMARY" in text


def test_build_messages_includes_observation():
    state = AgentState(task="fix bug")
    messages = build_messages(state, "some tool output")
    assert len(messages) == 1
    assert "some tool output" in messages[0]["content"]


def test_build_messages_without_observation():
    state = AgentState(task="fix bug")
    messages = build_messages(state, None)
    assert "LATEST TOOL OBSERVATION" not in messages[0]["content"]
