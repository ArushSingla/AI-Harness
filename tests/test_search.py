from src.tools.filesystem import Workspace
from src.tools.search import search_files


def test_search_finds_match(tmp_path):
    (tmp_path / "a.py").write_text("def login():\n    return 200\n")
    (tmp_path / "b.py").write_text("def logout():\n    return 200\n")
    ws = Workspace(str(tmp_path))
    result = search_files(ws, "login")
    assert result.ok
    assert "a.py" in result.output
    assert "b.py" not in result.output


def test_search_no_match(tmp_path):
    (tmp_path / "a.py").write_text("pass\n")
    ws = Workspace(str(tmp_path))
    result = search_files(ws, "nonexistent_token_xyz")
    assert result.ok
    assert "No matches" in result.output


def test_search_regex(tmp_path):
    (tmp_path / "a.py").write_text("def login_user():\n    pass\n")
    ws = Workspace(str(tmp_path))
    result = search_files(ws, r"def \w+_user", regex=True)
    assert result.ok
    assert "a.py" in result.output


def test_search_ignores_git_dir(tmp_path):
    gitdir = tmp_path / ".git"
    gitdir.mkdir()
    (gitdir / "config").write_text("login-secret-token\n")
    (tmp_path / "app.py").write_text("no match here\n")
    ws = Workspace(str(tmp_path))
    result = search_files(ws, "login-secret-token")
    assert result.ok
    assert "No matches" in result.output
