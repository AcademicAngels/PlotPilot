"""OpenAIProvider 测试"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from domain.ai.services.llm_service import GenerationConfig
from domain.ai.value_objects.prompt import Prompt
from infrastructure.ai.config.settings import Settings
from infrastructure.ai.providers.openai_provider import OpenAIProvider


class TestOpenAIProvider:
    """OpenAIProvider 测试"""

    @pytest.fixture
    def provider_with_client(self):
        """创建带 mock client 的 provider 实例"""
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock()
        mock_client.responses.create = AsyncMock()

        with patch("infrastructure.ai.providers.openai_provider.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = mock_client
            provider = OpenAIProvider(
                Settings(
                    api_key="test-api-key",
                    base_url="https://example.com/v1",
                    default_model="gpt-5.4",
                    timeout=45.0,
                    max_retries=4,
                    api_mode="auto",
                )
            )

        return provider, mock_client

    def test_initialization_passes_transport_settings(self):
        """测试初始化时传递 base_url、timeout 和重试参数"""
        with patch("infrastructure.ai.providers.openai_provider.AsyncOpenAI") as mock_openai:
            OpenAIProvider(
                Settings(
                    api_key="test-api-key",
                    base_url="https://gateway.example.com/v1",
                    default_model="gpt-5.4",
                    timeout=30.0,
                    max_retries=5,
                )
            )

        mock_openai.assert_called_once_with(
            api_key="test-api-key",
            timeout=30.0,
            max_retries=5,
            base_url="https://gateway.example.com/v1",
        )

    @pytest.mark.asyncio
    async def test_generate_builds_chat_completion_request(self, provider_with_client):
        """测试生成请求组装和结果映射"""
        provider, mock_client = provider_with_client
        prompt = Prompt.from_messages(
            [
                {"role": "developer", "content": "Keep JSON output"},
                {"role": "user", "content": "Summarize this scene"},
            ]
        )
        config = GenerationConfig(
            model="gpt-5.4",
            temperature=0.3,
            max_tokens=512,
            top_p=0.9,
            stop=["END"],
            seed=11,
            response_format={"type": "json_object"},
            tools=[{"type": "function", "function": {"name": "lookup"}}],
            tool_choice="auto",
            metadata={"trace_id": "abc"},
        )

        mock_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="{}",
                        tool_calls=[
                            SimpleNamespace(
                                id="call_1",
                                type="function",
                                function=SimpleNamespace(name="lookup", arguments="{}"),
                            )
                        ],
                    ),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=8),
            model="gpt-5.4",
        )

        result = await provider.generate(prompt, config)

        assert result.content == "{}"
        assert result.finish_reason == "stop"
        assert result.model == "gpt-5.4"
        assert result.provider == "openai-chat-completions"
        assert result.token_usage.total_tokens == 20
        assert result.tool_calls == [
            {
                "id": "call_1",
                "type": "function",
                "name": "lookup",
                "arguments": "{}",
            }
        ]

        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-5.4",
            messages=[
                {"role": "developer", "content": "Keep JSON output"},
                {"role": "user", "content": "Summarize this scene"},
            ],
            max_tokens=512,
            temperature=0.3,
            top_p=0.9,
            stop=["END"],
            seed=11,
            response_format={"type": "json_object"},
            tools=[{"type": "function", "function": {"name": "lookup"}}],
            tool_choice="auto",
            metadata={"trace_id": "abc"},
        )

    @pytest.mark.asyncio
    async def test_generate_rejects_empty_content(self, provider_with_client):
        """测试空响应内容抛出异常"""
        provider, mock_client = provider_with_client
        mock_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=""), finish_reason="stop")],
            usage=None,
            model="gpt-5.4",
        )

        with pytest.raises(RuntimeError, match="empty content"):
            await provider.generate(Prompt(system="sys", user="hello"), GenerationConfig())

    @pytest.mark.asyncio
    async def test_stream_generate_yields_delta_content(self, provider_with_client):
        """测试流式输出只产出文本 delta"""
        provider, mock_client = provider_with_client

        async def _stream():
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content="Hello"))]
            )
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content=" world"))]
            )
            yield SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content=None))]
            )

        mock_client.chat.completions.create.return_value = _stream()

        chunks = []
        async for chunk in provider.stream_generate(
            Prompt(system="sys", user="hello"),
            GenerationConfig(model="gpt-5.4"),
        ):
            chunks.append(chunk)

        assert chunks == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_reasoning_effort_is_safely_ignored_for_chat_completions(
        self,
        provider_with_client,
        caplog,
    ):
        """测试 reasoning 参数在当前路径安全降级"""
        provider, mock_client = provider_with_client
        mock_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"), finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            model="gpt-5.4",
        )

        await provider.generate(
            Prompt(system="sys", user="hello"),
            GenerationConfig(reasoning_effort="medium", api_mode="chat"),
        )

        assert "ignore protocol-level reasoning controls" in caplog.text

    @pytest.mark.asyncio
    async def test_generate_uses_responses_api_for_reasoning(self, provider_with_client):
        """测试 reasoning 触发 Responses API 路径"""
        provider, mock_client = provider_with_client
        mock_client.responses.create.return_value = SimpleNamespace(
            id="resp_123",
            output_text="reasoned answer",
            output=[
                SimpleNamespace(
                    type="function_call",
                    id="fc_1",
                    call_id="call_1",
                    name="lookup",
                    arguments="{\"id\":1}",
                )
            ],
            usage=SimpleNamespace(input_tokens=21, output_tokens=13),
            model="o4-mini",
            status="completed",
        )

        result = await provider.generate(
            Prompt.from_messages(
                [
                    {"role": "developer", "content": "Think carefully"},
                    {"role": "user", "content": "Solve this"},
                ]
            ),
            GenerationConfig(
                model="o4-mini",
                reasoning_effort="medium",
                previous_response_id="resp_prev",
                include=["reasoning.encrypted_content"],
                store=True,
                service_tier="auto",
                parallel_tool_calls=False,
            ),
        )

        assert result.content == "reasoned answer"
        assert result.provider == "openai-responses"
        assert result.finish_reason == "completed"
        assert result.token_usage.total_tokens == 34
        assert result.tool_calls == [
            {
                "id": "fc_1",
                "type": "function_call",
                "call_id": "call_1",
                "name": "lookup",
                "arguments": "{\"id\":1}",
            }
        ]

        mock_client.responses.create.assert_called_once_with(
            model="o4-mini",
            input=[
                {
                    "role": "developer",
                    "content": [{"type": "input_text", "text": "Think carefully"}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Solve this"}],
                },
            ],
            max_output_tokens=4096,
            temperature=1.0,
            previous_response_id="resp_prev",
            include=["reasoning.encrypted_content"],
            store=True,
            service_tier="auto",
            parallel_tool_calls=False,
            reasoning={"effort": "medium"},
        )

    @pytest.mark.asyncio
    async def test_stream_generate_uses_responses_events(self, provider_with_client):
        """测试 Responses API 流式事件解析"""
        provider, mock_client = provider_with_client

        async def _stream():
            yield SimpleNamespace(type="response.output_text.delta", delta="Hel")
            yield SimpleNamespace(type="response.output_text.delta", delta="lo")
            yield SimpleNamespace(type="response.output_text.done", text="!")

        mock_client.responses.create.return_value = _stream()

        chunks = []
        async for chunk in provider.stream_generate(
            Prompt(system="sys", user="hello"),
            GenerationConfig(api_mode="responses"),
        ):
            chunks.append(chunk)

        assert chunks == ["Hel", "lo", "!"]

    @pytest.mark.asyncio
    async def test_generate_runs_responses_tool_loop_when_executor_provided(self, provider_with_client):
        """测试 Responses tool call 能真实执行并续跑"""
        provider, mock_client = provider_with_client
        mock_client.responses.create.side_effect = [
            SimpleNamespace(
                id="resp_1",
                output_text="",
                output=[
                    SimpleNamespace(
                        type="function_call",
                        id="fc_1",
                        call_id="call_1",
                        name="lookup",
                        arguments="{\"query\":\"hero\"}",
                    )
                ],
                usage=SimpleNamespace(input_tokens=10, output_tokens=4),
                model="o4-mini",
                status="completed",
            ),
            SimpleNamespace(
                id="resp_2",
                output_text="tool-enriched answer",
                output=[],
                usage=SimpleNamespace(input_tokens=6, output_tokens=9),
                model="o4-mini",
                status="completed",
            ),
        ]

        tool_calls = []

        async def tool_executor(tool_call):
            tool_calls.append(tool_call)
            return {"result": "ok", "source": "kb"}

        result = await provider.generate(
            Prompt(system="sys", user="hello"),
            GenerationConfig(
                api_mode="responses",
                tools=[{"type": "function", "function": {"name": "lookup"}}],
                tool_executor=tool_executor,
            ),
        )

        assert len(tool_calls) == 1
        assert tool_calls[0]["name"] == "lookup"
        assert result.content == "tool-enriched answer"
        assert result.tool_calls is None
        assert mock_client.responses.create.call_count == 2

        second_call = mock_client.responses.create.call_args_list[1].kwargs
        assert second_call["previous_response_id"] == "resp_1"
        assert second_call["input"] == [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "{\"result\": \"ok\", \"source\": \"kb\"}",
            }
        ]

    @pytest.mark.asyncio
    async def test_generate_runs_chat_tool_loop_when_executor_provided(self, provider_with_client):
        """测试 Chat Completions tool call 能真实执行并续跑"""
        provider, mock_client = provider_with_client
        mock_client.chat.completions.create.side_effect = [
            SimpleNamespace(
                id="chatcmpl_1",
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="",
                            tool_calls=[
                                SimpleNamespace(
                                    id="call_1",
                                    type="function",
                                    function=SimpleNamespace(name="lookup", arguments="{\"q\":\"hero\"}"),
                                )
                            ],
                        ),
                        finish_reason="tool_calls",
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=4),
                model="gpt-5.4",
            ),
            SimpleNamespace(
                id="chatcmpl_2",
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="final answer", tool_calls=None),
                        finish_reason="stop",
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=4, completion_tokens=5),
                model="gpt-5.4",
            ),
        ]

        def tool_executor(tool_call):
            assert tool_call["name"] == "lookup"
            return {"chapter": 1}

        result = await provider.generate(
            Prompt(system="sys", user="hello"),
            GenerationConfig(
                api_mode="chat",
                tools=[{"type": "function", "function": {"name": "lookup"}}],
                tool_executor=tool_executor,
            ),
        )

        assert result.content == "final answer"
        assert mock_client.chat.completions.create.call_count == 2
        second_call = mock_client.chat.completions.create.call_args_list[1].kwargs
        assert second_call["messages"][-1] == {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": "{\"chapter\": 1}",
        }

    @pytest.mark.asyncio
    async def test_tool_messages_require_call_id_for_responses(self, provider_with_client):
        """测试 tool message 缺少 call_id 时阻止伪兼容"""
        provider, _ = provider_with_client

        with pytest.raises(ValueError, match="require call_id"):
            provider._to_responses_input(
                [
                    {"role": "user", "content": "hello"},
                    {"role": "tool", "content": "done"},
                ]
            )
