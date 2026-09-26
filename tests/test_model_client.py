import os

import pytest

from src.model.model_client import (
    AnthropicModelClient,
    MockModelClient,
    ModelError,
    build_model_client,
)


def test_mock_model_client_returns_scripted_responses():
    client = MockModelClient(["one", "two"])
    assert client.complete("sys", []) == "one"
    assert client.complete("sys", []) == "two"


def test_mock_model_client_repeats_last_when_exhausted():
    client = MockModelClient(["only"])
    assert client.complete("sys", []) == "only"
    assert client.complete("sys", []) == "only"


def test_mock_model_client_requires_nonempty_script():
    with pytest.raises(ValueError):
        MockModelClient([])


def test_anthropic_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("AI_API_KEY", raising=False)
    with pytest.raises(ModelError):
        AnthropicModelClient()


def test_anthropic_client_reads_api_key(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "fake-key-for-test")
    client = AnthropicModelClient()
    assert client.api_key == "fake-key-for-test"


def test_build_model_client_uses_mock_when_script_given():
    client = build_model_client(mock_script=["hi"])
    assert isinstance(client, MockModelClient)


def test_build_model_client_uses_real_client_by_default(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "fake-key-for-test")
    client = build_model_client()
    assert isinstance(client, AnthropicModelClient)
