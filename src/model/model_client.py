"""Text-only model client.

The agent talks to the model through a minimal, provider-agnostic interface:
`complete(system_prompt, messages) -> str`. The real implementation calls the
Anthropic Messages API over HTTPS using only the standard library (no SDK
dependency required). A MockModelClient is provided for tests and offline
demos so the harness can be exercised without spending a real API call.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import List, Dict

DEFAULT_MODEL = os.environ.get("AI_MODEL", "claude-sonnet-4-6")
API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class ModelError(Exception):
    pass


class ModelClient(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        """Return the model's text response for the given conversation."""


class AnthropicModelClient(ModelClient):
    """Calls the real Anthropic API. Requires AI_API_KEY in the environment."""

    def __init__(self, model: str | None = None, max_tokens: int = 2000, max_retries: int = 3):
        self.api_key = os.environ.get("AI_API_KEY")
        if not self.api_key:
            raise ModelError(
                "AI_API_KEY is not set. Export it before running the harness, e.g.\n"
                "  export AI_API_KEY=your-key-here"
            )
        self.model = model or DEFAULT_MODEL
        self.max_tokens = max_tokens
        self.max_retries = max_retries

    def complete(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": messages,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            API_URL,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": ANTHROPIC_VERSION,
            },
        )

        last_err: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
                return "".join(parts)
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", errors="ignore")
                if e.code == 429 or e.code >= 500:
                    last_err = ModelError(f"API error {e.code}: {detail}")
                    time.sleep(min(2 ** attempt, 10))
                    continue
                raise ModelError(f"API error {e.code}: {detail}") from e
            except urllib.error.URLError as e:
                last_err = ModelError(f"Network error calling model API: {e}")
                time.sleep(min(2 ** attempt, 10))
                continue
        raise last_err or ModelError("Model call failed after retries")


class MockModelClient(ModelClient):
    """Deterministic scripted client for tests and offline demos.

    `script` is a list of response strings returned in order, one per call.
    If the script is exhausted, the last response is repeated.
    """

    def __init__(self, script: List[str]):
        if not script:
            raise ValueError("MockModelClient requires at least one scripted response")
        self.script = script
        self.calls = 0

    def complete(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        idx = min(self.calls, len(self.script) - 1)
        response = self.script[idx]
        self.calls += 1
        return response


def build_model_client(mock_script: List[str] | None = None) -> ModelClient:
    """Factory used by the agent/CLI. Uses a mock client only if explicitly given a script
    (e.g. via --mock-script in tests/demo mode) — production runs always use the real API."""
    if mock_script is not None:
        return MockModelClient(mock_script)
    return AnthropicModelClient()
