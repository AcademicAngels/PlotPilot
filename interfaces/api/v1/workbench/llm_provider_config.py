"""LLM provider configuration endpoints for the workbench settings UI."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, HttpUrl, field_validator

from infrastructure.ai.config.runtime_llm_config import (
    apply_openai_compatible_env,
    persist_openai_compatible_config,
    read_openai_compatible_config,
)


router = APIRouter(prefix="/settings/llm-provider", tags=["llm-config"])


class OpenAICompatibleConfigResponse(BaseModel):
    llm_provider: Literal["anthropic", "openai"]
    has_api_key: bool
    api_key_masked: Optional[str] = None
    base_url: str
    model: str
    api_mode: Literal["auto", "chat", "responses"]
    timeout: int
    max_retries: int
    embedding_model: str
    embedding_dimension: Optional[int] = None
    examples: list[dict[str, str]]


class UpdateOpenAICompatibleConfigRequest(BaseModel):
    llm_provider: Literal["anthropic", "openai"] = "openai"
    api_key: Optional[str] = Field(default=None, description="Leave empty to keep the existing key")
    clear_api_key: bool = False
    base_url: HttpUrl
    model: str = Field(min_length=1, max_length=128)
    api_mode: Literal["auto", "chat", "responses"] = "auto"
    timeout: int = Field(default=120, ge=1, le=600)
    max_retries: int = Field(default=2, ge=0, le=10)
    embedding_model: str = Field(default="text-embedding-3-small", min_length=1, max_length=128)
    embedding_dimension: Optional[int] = Field(default=None, ge=1, le=32768)

    @field_validator("model", "embedding_model")
    @classmethod
    def strip_model_names(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("model fields cannot be empty")
        return normalized


def _examples() -> list[dict[str, str]]:
    return [
        {
            "name": "Chat Completions 网关",
            "llm_provider": "openai",
            "base_url": "https://your-gateway.example.com/v1",
            "model": "mimo-v2-pro",
            "api_mode": "chat",
            "notes": "适合只提供 /chat/completions 的 OpenAI 兼容网关。",
        },
        {
            "name": "Responses 原生兼容",
            "llm_provider": "openai",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-5.4",
            "api_mode": "responses",
            "notes": "适合原生 OpenAI 或明确支持 Responses API 的兼容服务。",
        },
        {
            "name": "自动分流",
            "llm_provider": "openai",
            "base_url": "https://your-router.example.com/v1",
            "model": "gpt-5.4",
            "api_mode": "auto",
            "notes": "默认推荐。普通文本走 chat，reasoning / previous_response_id 会切到 responses。",
        },
    ]


@router.get("", response_model=OpenAICompatibleConfigResponse)
async def get_llm_provider_config():
    snapshot = read_openai_compatible_config()
    return OpenAICompatibleConfigResponse(
        **snapshot.__dict__,
        examples=_examples(),
    )


@router.put("", response_model=OpenAICompatibleConfigResponse)
async def update_llm_provider_config(request: UpdateOpenAICompatibleConfigRequest):
    snapshot = read_openai_compatible_config()

    if request.clear_api_key:
        api_key: Optional[str] = None
    elif request.api_key is None or request.api_key.strip() == "":
        api_key = None if not snapshot.has_api_key else None
    else:
        api_key = request.api_key.strip()

    if request.llm_provider == "openai" and not (api_key or snapshot.has_api_key) and not request.clear_api_key:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY is required when LLM provider is openai")

    values: dict[str, Optional[str]] = {
        "LLM_PROVIDER": request.llm_provider,
        "OPENAI_BASE_URL": str(request.base_url).rstrip("/"),
        "OPENAI_MODEL": request.model,
        "OPENAI_API_MODE": request.api_mode,
        "OPENAI_TIMEOUT": str(request.timeout),
        "OPENAI_MAX_RETRIES": str(request.max_retries),
        "OPENAI_EMBEDDING_MODEL": request.embedding_model,
        "OPENAI_EMBEDDING_DIMENSION": (
            str(request.embedding_dimension) if request.embedding_dimension is not None else None
        ),
    }

    if request.clear_api_key:
        values["OPENAI_API_KEY"] = None
    elif api_key is not None:
        values["OPENAI_API_KEY"] = api_key

    persist_openai_compatible_config(values)
    apply_openai_compatible_env(values)

    refreshed = read_openai_compatible_config()
    return OpenAICompatibleConfigResponse(
        **refreshed.__dict__,
        examples=_examples(),
    )
