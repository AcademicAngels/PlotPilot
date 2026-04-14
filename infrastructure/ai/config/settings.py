"""AI 配置设置"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Settings:
    """AI 配置设置

    管理 LLM 提供商的配置参数。
    """

    default_model: str = "claude-3-5-sonnet-20241022"
    default_temperature: float = 0.7
    default_max_tokens: int = 4096
    api_key: Optional[str] = None
    #: 兼容自建/转发网关，与官方 ANTHROPIC_BASE_URL 一致；未设则走官方默认
    base_url: Optional[str] = None
    timeout: float = 120.0
    max_retries: int = 2
    api_mode: str = "auto"

    def __post_init__(self):
        """验证配置参数"""
        if not (0.0 <= self.default_temperature <= 2.0):
            raise ValueError("Temperature must be between 0.0 and 2.0")

        if self.default_max_tokens <= 0:
            raise ValueError("Max tokens must be positive")

        if self.timeout <= 0:
            raise ValueError("Timeout must be positive")

        if self.max_retries < 0:
            raise ValueError("Max retries cannot be negative")

        if self.api_mode not in {"auto", "chat", "responses"}:
            raise ValueError("api_mode must be one of: auto, chat, responses")
