"""CLI entry point for the AI Harness autonomous coding agent."""
from __future__ import annotations

import argparse
import os
import sys

from src.agent.loop import AgentLoop
from src.model.model_client import build_model_client, ModelError
from src.tools.filesystem import Workspace, PathSafetyError
from src.ui import tui


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autonomous coding agent harness")
    parser.add_argument("--repo", required=True, help="Path to the target git repository/workspace")
    parser.add_argument("--task", required=True, help="Natural-language description of the task/issue")
    parser.add_argument(
        "--mock-script",
        help="Path to a JSON file with a list of scripted model responses (offline demo/testing only)",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    try:
        workspace = Workspace(args.repo)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except PathSafetyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    mock_script = None
    if args.mock_script:
        import json
        with open(args.mock_script) as f:
            mock_script = json.load(f)

    try:
        model = build_model_client(mock_script=mock_script)
    except ModelError as e:
        print(f"Error: {e}", file=sys.stderr)
        print(
            "Set AI_API_KEY in your environment, e.g.:\n  export AI_API_KEY=your-key-here",
            file=sys.stderr,
        )
        return 3

    tui.print_header(str(workspace.root), args.task)
    loop = AgentLoop(workspace, model, args.task, on_activity=tui.make_activity_printer())
    try:
        result = loop.run()
    except Exception as e:  # pragma: no cover - top-level safety net
        print(f"\nUnexpected internal error: {e}", file=sys.stderr)
        return 1

    tui.print_final(result.state, result.verification_text)
    return 0 if result.state.success else 1


if __name__ == "__main__":
    sys.exit(main())
