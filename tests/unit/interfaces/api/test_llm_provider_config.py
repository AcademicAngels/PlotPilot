"""Tests for LLM provider configuration endpoints."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from interfaces.api.v1.workbench import llm_provider_config


@pytest.mark.asyncio
async def test_get_llm_provider_config(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://router.example.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.4")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")

    data = (await llm_provider_config.get_llm_provider_config()).model_dump()
    assert data["llm_provider"] == "openai"
    assert data["base_url"] == "https://router.example.com/v1"
    assert data["model"] == "gpt-5.4"
    assert data["has_api_key"] is True
    assert len(data["examples"]) >= 2


@pytest.mark.asyncio
async def test_update_llm_provider_config_requires_key_when_switching_to_openai(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")

    request = llm_provider_config.UpdateOpenAICompatibleConfigRequest(
        llm_provider="openai",
        base_url="https://router.example.com/v1",
        model="gpt-5.4",
        api_mode="chat",
        timeout=120,
        max_retries=2,
        embedding_model="text-embedding-3-small",
        embedding_dimension=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        await llm_provider_config.update_llm_provider_config(request)
    assert "OPENAI_API_KEY is required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_update_llm_provider_config_persists_values(monkeypatch):
    captured = {}

    def fake_persist(values):
        captured["persist"] = values

    def fake_apply(values):
        captured["apply"] = values
        monkeypatch.setenv("LLM_PROVIDER", values["LLM_PROVIDER"])
        monkeypatch.setenv("OPENAI_BASE_URL", values["OPENAI_BASE_URL"])
        monkeypatch.setenv("OPENAI_MODEL", values["OPENAI_MODEL"])
        monkeypatch.setenv("OPENAI_API_MODE", values["OPENAI_API_MODE"])
        monkeypatch.setenv("OPENAI_TIMEOUT", values["OPENAI_TIMEOUT"])
        monkeypatch.setenv("OPENAI_MAX_RETRIES", values["OPENAI_MAX_RETRIES"])
        monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", values["OPENAI_EMBEDDING_MODEL"])
        monkeypatch.setenv("OPENAI_API_KEY", values["OPENAI_API_KEY"])

    monkeypatch.setattr(llm_provider_config, "persist_openai_compatible_config", fake_persist)
    monkeypatch.setattr(llm_provider_config, "apply_openai_compatible_env", fake_apply)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-old")

    request = llm_provider_config.UpdateOpenAICompatibleConfigRequest(
        llm_provider="openai",
        api_key="sk-new",
        base_url="https://router.example.com/v1",
        model="gpt-5.4",
        api_mode="responses",
        timeout=90,
        max_retries=4,
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
    )

    response = await llm_provider_config.update_llm_provider_config(request)

    assert captured["persist"]["OPENAI_API_KEY"] == "sk-new"
    assert captured["apply"]["OPENAI_API_MODE"] == "responses"
    assert response.base_url == "https://router.example.com/v1"
    assert response.api_mode == "responses"
