# domain/ai/services/llm_service.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional, Union
from domain.ai.value_objects.prompt import Prompt
from domain.ai.value_objects.token_usage import TokenUsage

ToolExecutor = Callable[[Dict[str, Any]], Union[Any, Awaitable[Any]]]


@dataclass
class GenerationConfig:
    """生成配置"""
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 4096
    temperature: float = 1.0
    top_p: Optional[float] = None
    stop: Optional[List[str]] = None
    seed: Optional[int] = None
    response_format: Optional[Dict[str, Any]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Any] = None
    reasoning_effort: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timeout: Optional[float] = None
    api_mode: Optional[str] = None
    previous_response_id: Optional[str] = None
    include: Optional[List[str]] = None
    store: Optional[bool] = None
    service_tier: Optional[str] = None
    parallel_tool_calls: Optional[bool] = None
    tool_executor: Optional[ToolExecutor] = None
    max_tool_roundtrips: int = 3

    def __post_init__(self):
        """验证配置参数"""
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError("Temperature must be between 0.0 and 2.0")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be greater than 0")
        if self.top_p is not None and not (0.0 <= self.top_p <= 1.0):
            raise ValueError("top_p must be between 0.0 and 1.0")
        if self.stop is not None:
            if not isinstance(self.stop, list) or not all(
                isinstance(item, str) and item for item in self.stop
            ):
                raise ValueError("stop must be a list of non-empty strings")
        if self.seed is not None and not isinstance(self.seed, int):
            raise ValueError("seed must be an integer")
        if self.response_format is not None and not isinstance(self.response_format, dict):
            raise ValueError("response_format must be a dictionary")
        if self.tools is not None and not isinstance(self.tools, list):
            raise ValueError("tools must be a list")
        if self.metadata is not None and not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError("timeout must be greater than 0")
        if self.max_tool_roundtrips <= 0:
            raise ValueError("max_tool_roundtrips must be greater than 0")
        if self.api_mode is not None:
            normalized_api_mode = self.api_mode.strip().lower()
            if normalized_api_mode not in {"auto", "chat", "responses"}:
                raise ValueError("api_mode must be one of: auto, chat, responses")
            self.api_mode = normalized_api_mode
        if self.reasoning_effort is not None:
            allowed = {"none", "minimal", "low", "medium", "high"}
            normalized = self.reasoning_effort.strip().lower()
            if normalized not in allowed:
                raise ValueError(
                    "reasoning_effort must be one of: none, minimal, low, medium, high"
                )
            self.reasoning_effort = normalized


@dataclass
class GenerationResult:
    """生成结果"""
    content: str
    token_usage: TokenUsage
    finish_reason: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    raw_response: Optional[Any] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    response_id: Optional[str] = None

    def __post_init__(self):
        """验证结果参数"""
        has_content = bool(self.content and self.content.strip())
        has_tool_calls = bool(self.tool_calls)
        if not has_content and not has_tool_calls:
            raise ValueError("Content cannot be empty")
        if self.tool_calls is not None and not isinstance(self.tool_calls, list):
            raise ValueError("tool_calls must be a list when provided")


class LLMService(ABC):
    """LLM 服务接口（领域服务）"""

    @abstractmethod
    async def generate(
        self,
        prompt: Prompt,
        config: GenerationConfig
    ) -> GenerationResult:
        """生成内容"""
        pass

    @abstractmethod
    async def stream_generate(
        self,
        prompt: Prompt,
        config: GenerationConfig
    ) -> AsyncIterator[str]:
        """流式生成内容"""
        pass
