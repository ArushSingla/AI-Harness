import pytest

from src.tools.filesystem import Workspace, PathSafetyError


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hello')\n")
    (tmp_path / "README.md").write_text("# demo\n")
    return Workspace(str(tmp_path))


def test_list_files(ws):
    result = ws.list_files(".")
    assert result.ok
    assert "README.md" in result.output
    assert "src/" in result.output


def test_read_file(ws):
    result = ws.read_file("src/app.py")
    assert result.ok
    assert "hello" in result.output


def test_read_file_missing(ws):
    result = ws.read_file("nope.py")
    assert not result.ok


def test_write_file_creates_dirs(ws):
    result = ws.write_file("new/dir/file.txt", "hi")
    assert result.ok
    assert (ws.root / "new" / "dir" / "file.txt").read_text() == "hi"


def test_edit_file_unique_match(ws):
    result = ws.edit_file("src/app.py", "hello", "world")
    assert result.ok
    assert "world" in (ws.root / "src" / "app.py").read_text()


def test_edit_file_requires_unique_match(ws):
    (ws.root / "dup.py").write_text("x\nx\n")
    result = ws.edit_file("dup.py", "x", "y")
    assert not result.ok
    assert "matches 2 times" in result.output


def test_edit_file_no_match(ws):
    result = ws.edit_file("src/app.py", "does-not-exist", "y")
    assert not result.ok


def test_delete_file(ws):
    result = ws.delete_file("README.md")
    assert result.ok
    assert not (ws.root / "README.md").exists()


def test_delete_directory_refused(ws):
    result = ws.delete_file("src")
    assert not result.ok


def test_path_traversal_blocked_on_read(ws):
    result = ws.read_file("../../../etc/passwd")
    assert not result.ok
    assert "outside the workspace" in result.output


def test_path_traversal_blocked_on_write(ws):
    result = ws.write_file("../escape.txt", "x")
    assert not result.ok


def test_resolve_raises_for_absolute_escape(ws):
    with pytest.raises(PathSafetyError):
        ws.resolve("/etc/passwd")
