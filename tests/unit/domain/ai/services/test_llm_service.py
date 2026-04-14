# tests/unit/domain/ai/services/test_llm_service.py
import pytest
from domain.ai.services.llm_service import GenerationConfig, GenerationResult
from domain.ai.value_objects.token_usage import TokenUsage


class TestGenerationConfig:
    """测试 GenerationConfig 验证"""

    def test_generation_config_creation(self):
        """测试创建 GenerationConfig"""
        config = GenerationConfig(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            temperature=1.0
        )
        assert config.model == "claude-3-5-sonnet-20241022"
        assert config.max_tokens == 4096
        assert config.temperature == 1.0

    def test_generation_config_default_values(self):
        """测试默认值"""
        config = GenerationConfig()
        assert config.model == "claude-sonnet-4-6"
        assert config.max_tokens == 4096
        assert config.temperature == 1.0
        assert config.reasoning_effort is None

    def test_generation_config_extended_values(self):
        """测试扩展字段"""
        config = GenerationConfig(
            top_p=0.8,
            stop=["END"],
            seed=7,
            response_format={"type": "json_object"},
            tools=[{"type": "function", "function": {"name": "lookup"}}],
            tool_choice="auto",
            reasoning_effort="HIGH",
            metadata={"trace_id": "abc"},
            timeout=45.0,
        )

        assert config.top_p == 0.8
        assert config.stop == ["END"]
        assert config.seed == 7
        assert config.response_format == {"type": "json_object"}
        assert config.tools[0]["function"]["name"] == "lookup"
        assert config.tool_choice == "auto"
        assert config.reasoning_effort == "high"
        assert config.metadata == {"trace_id": "abc"}
        assert config.timeout == 45.0
        assert config.api_mode is None

    def test_generation_config_temperature_below_zero_raises_error(self):
        """测试温度小于 0 抛出异常"""
        with pytest.raises(ValueError, match="Temperature must be between 0.0 and 2.0"):
            GenerationConfig(temperature=-0.1)

    def test_generation_config_temperature_above_two_raises_error(self):
        """测试温度大于 2.0 抛出异常"""
        with pytest.raises(ValueError, match="Temperature must be between 0.0 and 2.0"):
            GenerationConfig(temperature=2.1)

    def test_generation_config_max_tokens_zero_raises_error(self):
        """测试 max_tokens 为 0 抛出异常"""
        with pytest.raises(ValueError, match="max_tokens must be greater than 0"):
            GenerationConfig(max_tokens=0)

    def test_generation_config_max_tokens_negative_raises_error(self):
        """测试 max_tokens 为负数抛出异常"""
        with pytest.raises(ValueError, match="max_tokens must be greater than 0"):
            GenerationConfig(max_tokens=-1)

    def test_generation_config_valid_temperature_boundaries(self):
        """测试温度边界值"""
        config_min = GenerationConfig(temperature=0.0)
        assert config_min.temperature == 0.0

        config_max = GenerationConfig(temperature=2.0)
        assert config_max.temperature == 2.0

    def test_generation_config_invalid_reasoning_effort_raises_error(self):
        """测试非法 reasoning_effort 抛出异常"""
        with pytest.raises(ValueError, match="reasoning_effort must be one of"):
            GenerationConfig(reasoning_effort="ultra")

    def test_generation_config_invalid_api_mode_raises_error(self):
        """测试非法 api_mode 抛出异常"""
        with pytest.raises(ValueError, match="api_mode must be one of"):
            GenerationConfig(api_mode="legacy")


class TestGenerationResult:
    """测试 GenerationResult 验证"""

    def test_generation_result_creation(self):
        """测试创建 GenerationResult"""
        token_usage = TokenUsage(input_tokens=100, output_tokens=200)
        result = GenerationResult(
            content="生成的内容",
            token_usage=token_usage,
            finish_reason="stop",
            model="gpt-5.4",
            provider="openai",
            raw_response={"id": "resp_1"},
            tool_calls=[{"id": "call_1"}],
        )
        assert result.content == "生成的内容"
        assert result.token_usage.input_tokens == 100
        assert result.token_usage.output_tokens == 200
        assert result.finish_reason == "stop"
        assert result.model == "gpt-5.4"
        assert result.provider == "openai"
        assert result.raw_response == {"id": "resp_1"}
        assert result.tool_calls == [{"id": "call_1"}]

    def test_generation_result_allows_tool_calls_without_content(self):
        """测试仅 tool_calls 的中间态结果合法"""
        result = GenerationResult(
            content="",
            token_usage=TokenUsage(input_tokens=1, output_tokens=1),
            tool_calls=[{"id": "call_1"}],
        )
        assert result.tool_calls == [{"id": "call_1"}]

    def test_generation_result_empty_content_raises_error(self):
        """测试空内容抛出异常"""
        token_usage = TokenUsage(input_tokens=100, output_tokens=200)
        with pytest.raises(ValueError, match="Content cannot be empty"):
            GenerationResult(content="", token_usage=token_usage)

    def test_generation_result_whitespace_only_content_raises_error(self):
        """测试仅空白字符的内容抛出异常"""
        token_usage = TokenUsage(input_tokens=100, output_tokens=200)
        with pytest.raises(ValueError, match="Content cannot be empty"):
            GenerationResult(content="   ", token_usage=token_usage)

    def test_generation_result_negative_input_tokens_raises_error(self):
        """测试负数 input_tokens 抛出异常"""
        with pytest.raises(ValueError, match="Token counts cannot be negative"):
            token_usage = TokenUsage(input_tokens=-1, output_tokens=200)
            GenerationResult(content="内容", token_usage=token_usage)

    def test_generation_result_negative_output_tokens_raises_error(self):
        """测试负数 output_tokens 抛出异常"""
        with pytest.raises(ValueError, match="Token counts cannot be negative"):
            token_usage = TokenUsage(input_tokens=100, output_tokens=-1)
            GenerationResult(content="内容", token_usage=token_usage)
