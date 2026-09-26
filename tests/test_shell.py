from src.tools.filesystem import Workspace
from src.tools.shell import run_command, is_dangerous


def test_runs_simple_command(tmp_path):
    ws = Workspace(str(tmp_path))
    result = run_command(ws, "echo hello")
    assert result.ok
    assert "hello" in result.output


def test_captures_nonzero_exit(tmp_path):
    ws = Workspace(str(tmp_path))
    result = run_command(ws, "exit 3")
    assert not result.ok
    assert result.data["exit_code"] == 3


def test_blocks_rm_rf_root(tmp_path):
    ws = Workspace(str(tmp_path))
    result = run_command(ws, "rm -rf /")
    assert not result.ok
    assert "BLOCKED" in result.output


def test_blocks_git_reset_hard(tmp_path):
    ws = Workspace(str(tmp_path))
    result = run_command(ws, "git reset --hard")
    assert not result.ok
    assert "BLOCKED" in result.output


def test_allows_safe_rm(tmp_path):
    (tmp_path / "junk.txt").write_text("x")
    ws = Workspace(str(tmp_path))
    result = run_command(ws, "rm junk.txt")
    assert result.ok


def test_is_dangerous_detects_fork_bomb():
    assert is_dangerous(":(){:|:&};:") is not None


def test_is_dangerous_allows_normal_command():
    assert is_dangerous("npm test") is None
