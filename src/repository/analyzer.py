"""Builds a lightweight repository map without reading every file."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from src.tools.filesystem import Workspace, DEFAULT_IGNORE_DIRS

README_NAMES = ["README.md", "README.rst", "README.txt", "README"]
MANIFESTS = ["package.json", "requirements.txt", "pyproject.toml", "go.mod", "Cargo.toml", "pom.xml", "build.gradle"]


@dataclass
class RepoSummary:
    language: str = "unknown"
    package_manager: str = "unknown"
    test_framework: str = "unknown"
    entry_points: List[str] = field(default_factory=list)
    top_level: List[str] = field(default_factory=list)
    readme_excerpt: str = ""
    manifests_found: List[str] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [
            f"language: {self.language}",
            f"package_manager: {self.package_manager}",
            f"test_framework: {self.test_framework}",
            f"entry_points: {', '.join(self.entry_points) or 'none detected'}",
            f"top_level: {', '.join(self.top_level)}",
        ]
        if self.readme_excerpt:
            lines.append(f"readme_excerpt: {self.readme_excerpt[:400]}")
        return "\n".join(lines)


def analyze_repository(workspace: Workspace) -> RepoSummary:
    root = workspace.root
    summary = RepoSummary()

    summary.top_level = sorted(
        p.name for p in root.iterdir()
        if not p.name.startswith(".") and p.name not in DEFAULT_IGNORE_DIRS
    )[:60]

    for name in README_NAMES:
        p = root / name
        if p.exists():
            try:
                summary.readme_excerpt = p.read_text(errors="ignore")[:1000]
            except Exception:
                pass
            break

    summary.manifests_found = [m for m in MANIFESTS if (root / m).exists()]

    if (root / "package.json").exists():
        summary.language = "javascript/typescript"
        try:
            data = json.loads((root / "package.json").read_text())
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "jest" in deps:
                summary.test_framework = "jest"
            elif "mocha" in deps:
                summary.test_framework = "mocha"
            elif "test" in data.get("scripts", {}):
                summary.test_framework = "npm-script"
            summary.package_manager = "yarn" if (root / "yarn.lock").exists() else "npm"
            main = data.get("main")
            if main:
                summary.entry_points.append(main)
        except Exception:
            pass
    elif (root / "requirements.txt").exists() or (root / "pyproject.toml").exists() or list(root.glob("*.py")):
        summary.language = "python"
        summary.package_manager = "pip"
        if (root / "pytest.ini").exists() or (root / "conftest.py").exists() or list(root.glob("test_*.py")) or (root / "tests").exists():
            summary.test_framework = "pytest"
        for candidate in ["main.py", "app.py", "manage.py", "src/main.py"]:
            if (root / candidate).exists():
                summary.entry_points.append(candidate)
    elif (root / "go.mod").exists():
        summary.language = "go"
        summary.package_manager = "go modules"
        summary.test_framework = "go test"
    elif (root / "Cargo.toml").exists():
        summary.language = "rust"
        summary.package_manager = "cargo"
        summary.test_framework = "cargo test"

    return summary
