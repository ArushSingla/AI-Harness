from src.tools.filesystem import Workspace
from src.repository.analyzer import analyze_repository


def test_detects_python_pytest_project(tmp_path):
    (tmp_path / "app.py").write_text("def add(a, b):\n    return a + b\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text("from app import add\n")
    (tmp_path / "README.md").write_text("# My Project\nDoes things.\n")
    ws = Workspace(str(tmp_path))
    summary = analyze_repository(ws)
    assert summary.language == "python"
    assert summary.test_framework == "pytest"
    assert "My Project" in summary.readme_excerpt


def test_detects_node_project(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"name": "demo", "scripts": {"test": "jest"}, "devDependencies": {"jest": "^29.0.0"}}'
    )
    ws = Workspace(str(tmp_path))
    summary = analyze_repository(ws)
    assert summary.language == "javascript/typescript"
    assert summary.test_framework == "jest"
    assert summary.package_manager == "npm"


def test_unknown_project_type(tmp_path):
    (tmp_path / "notes.txt").write_text("nothing special")
    ws = Workspace(str(tmp_path))
    summary = analyze_repository(ws)
    assert summary.language == "unknown"
