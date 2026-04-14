"""Tests for runtime-persisted LLM provider configuration helpers."""
from __future__ import annotations

from pathlib import Path

from infrastructure.ai.config.runtime_llm_config import (
    apply_openai_compatible_env,
    persist_openai_compatible_config,
    read_openai_compatible_config,
)


def test_persist_openai_compatible_config_preserves_unmanaged_keys(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# existing\n"
        "ANTHROPIC_API_KEY=test-anthropic\n"
        "OPENAI_MODEL=old-model\n",
        encoding="utf-8",
    )

    persist_openai_compatible_config(
        {
            "LLM_PROVIDER": "openai",
            "OPENAI_MODEL": "gpt-5.4",
            "OPENAI_BASE_URL": "https://gateway.example.com/v1",
        },
        path=env_path,
    )

    content = env_path.read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY=test-anthropic" in content
    assert "LLM_PROVIDER=openai" in content
    assert "OPENAI_MODEL=gpt-5.4" in content
    assert "OPENAI_BASE_URL=https://gateway.example.com/v1" in content


def test_apply_openai_compatible_env_updates_process_env(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    apply_openai_compatible_env(
        {
            "OPENAI_BASE_URL": "https://router.example.com/v1",
            "OPENAI_MODEL": "mimo-v2-pro",
        }
    )

    snapshot = read_openai_compatible_config()
    assert snapshot.base_url == "https://router.example.com/v1"
    assert snapshot.model == "mimo-v2-pro"


def test_read_openai_compatible_config_masks_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-example-secret")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.4")

    snapshot = read_openai_compatible_config()

    assert snapshot.has_api_key is True
    assert snapshot.api_key_masked == "sk-e***cret"
