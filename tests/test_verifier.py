import subprocess

from src.agent.verifier import verify
from src.tools.filesystem import Workspace


def _init_git_repo(root):
    subprocess.run(["git", "init", "-q"], cwd=root)
    subprocess.run(["git", "config", "user.email", "a@b.com"], cwd=root)
    subprocess.run(["git", "config", "user.name", "test"], cwd=root)


def test_verify_reports_passing_tests(tmp_path):
    _init_git_repo(tmp_path)
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert 1 == 1\n")
    ws = Workspace(str(tmp_path))
    report = verify(ws)
    assert report.tests_ran
    assert report.tests_passed


def test_verify_reports_failing_tests(tmp_path):
    _init_git_repo(tmp_path)
    (tmp_path / "test_bad.py").write_text("def test_bad():\n    assert 1 == 2\n")
    ws = Workspace(str(tmp_path))
    report = verify(ws)
    assert report.tests_ran
    assert not report.tests_passed


def test_verify_detects_diff(tmp_path):
    _init_git_repo(tmp_path)
    (tmp_path / "a.txt").write_text("v1\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path)
    (tmp_path / "a.txt").write_text("v2\n")
    ws = Workspace(str(tmp_path))
    report = verify(ws)
    assert report.has_diff
