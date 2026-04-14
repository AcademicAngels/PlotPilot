"""OpenAI LLM 提供商实现"""
import json
import logging
import os
from inspect import isawaitable
from typing import Any, AsyncIterator, Dict, Iterable, List, Optional

from openai import AsyncOpenAI

from domain.ai.services.llm_service import GenerationConfig, GenerationResult
from domain.ai.value_objects.prompt import Prompt
from domain.ai.value_objects.token_usage import TokenUsage
from infrastructure.ai.config.settings import Settings
from .base import BaseProvider

logger = logging.getLogger(__name__)

# 从环境变量读取模型配置，默认使用 gpt-5.4
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4")


class OpenAIProvider(BaseProvider):
    """OpenAI LLM 提供商实现
    
    使用 OpenAI API 实现 LLM 服务。
    """

    def __init__(self, settings: Settings):
        """初始化 OpenAI 提供商
        
        Args:
            settings: AI 配置设置
            
        Raises:
            ValueError: 如果 API key 未设置
        """
        super().__init__(settings)
        
        if not settings.api_key:
            raise ValueError("API key is required for OpenAIProvider")
            
        # 初始化 AsyncOpenAI 客户端
        client_kwargs = {
            "api_key": settings.api_key,
            "timeout": settings.timeout,
            "max_retries": settings.max_retries,
        }
        if settings.base_url:
            client_kwargs["base_url"] = settings.base_url
            
        self.async_client = AsyncOpenAI(**client_kwargs)
        self.default_model = settings.default_model or DEFAULT_MODEL
        self.api_mode = settings.api_mode

    async def generate(
        self,
        prompt: Prompt,
        config: GenerationConfig
    ) -> GenerationResult:
        """生成文本
        
        Args:
            prompt: 提示词
            config: 生成配置
            
        Returns:
            生成结果
            
        Raises:
            RuntimeError: 当 API 调用失败或返回空内容时
        """
        try:
            if self._should_use_responses_api(config):
                result = await self._generate_via_responses(prompt, config)
                return await self._continue_with_tools_if_needed(
                    result,
                    prompt,
                    config,
                    use_responses_api=True,
                )

            result = await self._generate_via_chat_completions(prompt, config)
            return await self._continue_with_tools_if_needed(
                result,
                prompt,
                config,
                use_responses_api=False,
            )

        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to generate text: {type(e).__name__}: {str(e)}") from e

    async def stream_generate(
        self,
        prompt: Prompt,
        config: GenerationConfig
    ) -> AsyncIterator[str]:
        """流式生成内容
        
        Args:
            prompt: 提示词
            config: 生成配置
            
        Yields:
            生成的文本片段
            
        Raises:
            RuntimeError: 当流式生成失败时
        """
        try:
            if self._should_use_responses_api(config):
                async for content in self._stream_generate_via_responses(prompt, config):
                    yield content
                return

            async for content in self._stream_generate_via_chat_completions(prompt, config):
                yield content
                    
        except Exception as e:
            logger.error(f"[Stream] Failed: {e}")
            raise RuntimeError(f"Failed to stream text: {type(e).__name__}: {str(e)}") from e

    async def _generate_via_chat_completions(
        self,
        prompt: Prompt,
        config: GenerationConfig,
    ) -> GenerationResult:
        response = await self.async_client.chat.completions.create(
            **self._build_chat_request_payload(prompt, config)
        )
        return self._result_from_chat_response(response, config)

    async def _generate_via_responses(
        self,
        prompt: Prompt,
        config: GenerationConfig,
    ) -> GenerationResult:
        response = await self.async_client.responses.create(
            **self._build_responses_request_payload(prompt, config)
        )
        return self._result_from_responses_response(response, config)

    async def _stream_generate_via_chat_completions(
        self,
        prompt: Prompt,
        config: GenerationConfig,
    ) -> AsyncIterator[str]:
        stream = await self.async_client.chat.completions.create(
            **self._build_chat_request_payload(prompt, config, stream=True)
        )

        async for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue

            delta = getattr(choices[0], "delta", None)
            if delta is None:
                continue

            content = self._extract_text(getattr(delta, "content", None))
            if content:
                yield content

    async def _stream_generate_via_responses(
        self,
        prompt: Prompt,
        config: GenerationConfig,
    ) -> AsyncIterator[str]:
        stream = await self.async_client.responses.create(
            **self._build_responses_request_payload(prompt, config, stream=True)
        )

        async for event in stream:
            text = self._extract_responses_stream_text(event)
            if text:
                yield text

    def _should_use_responses_api(self, config: GenerationConfig) -> bool:
        api_mode = config.api_mode or self.api_mode
        if api_mode == "responses":
            return True
        if api_mode == "chat":
            return False

        return any(
            (
                config.reasoning_effort is not None,
                config.previous_response_id is not None,
                bool(config.include),
                config.store is not None,
                config.service_tier is not None,
                config.parallel_tool_calls is not None,
            )
        )

    def _build_chat_request_payload(
        self,
        prompt: Prompt,
        config: GenerationConfig,
        stream: bool = False,
    ) -> Dict[str, Any]:
        if config.reasoning_effort:
            logger.warning(
                "reasoning_effort=%s was requested, but the current OpenAIProvider path "
                "uses chat.completions and will ignore protocol-level reasoning controls.",
                config.reasoning_effort,
            )

        payload: Dict[str, Any] = {
            "model": config.model or self.default_model,
            "messages": prompt.to_messages(),
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
        }

        optional_fields = {
            "top_p": config.top_p,
            "stop": config.stop,
            "seed": config.seed,
            "response_format": config.response_format,
            "tools": config.tools,
            "tool_choice": config.tool_choice,
            "metadata": config.metadata,
        }

        for field_name, value in optional_fields.items():
            if value is not None:
                payload[field_name] = value

        if stream:
            payload["stream"] = True

        return payload

    def _build_responses_request_payload(
        self,
        prompt: Prompt,
        config: GenerationConfig,
        stream: bool = False,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": config.model or self.default_model,
            "input": self._to_responses_input(prompt.to_messages()),
            "max_output_tokens": config.max_tokens,
        }

        optional_fields = {
            "temperature": config.temperature,
            "top_p": config.top_p,
            "tools": config.tools,
            "tool_choice": config.tool_choice,
            "metadata": config.metadata,
            "previous_response_id": config.previous_response_id,
            "include": config.include,
            "store": config.store,
            "service_tier": config.service_tier,
            "parallel_tool_calls": config.parallel_tool_calls,
        }

        for field_name, value in optional_fields.items():
            if value is not None:
                payload[field_name] = value

        if config.reasoning_effort:
            payload["reasoning"] = {"effort": config.reasoning_effort}

        if stream:
            payload["stream"] = True

        return payload

    def _to_responses_input(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for message in messages:
            role = message.get("role")
            content = message.get("content")

            if role in {"tool", "function"}:
                call_id = (
                    message.get("call_id")
                    or message.get("tool_call_id")
                    or message.get("id")
                )
                if not call_id:
                    raise ValueError(
                        "Responses API tool/function messages require call_id or tool_call_id"
                    )
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": self._coerce_content_to_text(content),
                    }
                )
                continue

            items.append(
                {
                    "role": role,
                    "content": [
                        {
                            "type": "input_text",
                            "text": self._coerce_content_to_text(content),
                        }
                    ],
                }
            )

        return items

    async def _continue_with_tools_if_needed(
        self,
        result: GenerationResult,
        prompt: Prompt,
        config: GenerationConfig,
        *,
        use_responses_api: bool,
    ) -> GenerationResult:
        if not result.tool_calls or config.tool_executor is None:
            return result

        if use_responses_api:
            return await self._run_responses_tool_loop(result, prompt, config)

        return await self._run_chat_tool_loop(result, prompt, config)

    async def _run_responses_tool_loop(
        self,
        initial_result: GenerationResult,
        prompt: Prompt,
        config: GenerationConfig,
    ) -> GenerationResult:
        current_result = initial_result

        for _ in range(config.max_tool_roundtrips):
            if not current_result.tool_calls:
                return current_result

            if not current_result.response_id:
                raise RuntimeError("Responses tool loop requires response_id from previous response")

            tool_outputs = await self._execute_tool_calls(current_result.tool_calls, config)
            response = await self.async_client.responses.create(
                **self._build_responses_followup_payload(config, current_result.response_id, tool_outputs)
            )

            current_result = self._result_from_responses_response(response, config)

        if current_result.tool_calls:
            raise RuntimeError(
                f"Responses tool loop exceeded max_tool_roundtrips={config.max_tool_roundtrips}"
            )

        return current_result

    async def _run_chat_tool_loop(
        self,
        initial_result: GenerationResult,
        prompt: Prompt,
        config: GenerationConfig,
    ) -> GenerationResult:
        message_history = prompt.to_messages()
        current_result = initial_result
        current_response = current_result.raw_response

        for _ in range(config.max_tool_roundtrips):
            if not current_result.tool_calls:
                return current_result

            assistant_message = self._chat_assistant_message_from_result(current_response, current_result)
            if assistant_message:
                message_history.append(assistant_message)

            tool_messages = await self._build_chat_tool_messages(current_result.tool_calls, config)
            message_history.extend(tool_messages)

            response = await self.async_client.chat.completions.create(
                **self._build_chat_request_payload_from_messages(message_history, config)
            )
            current_response = response
            current_result = self._result_from_chat_response(response, config)

        if current_result.tool_calls:
            raise RuntimeError(
                f"Chat tool loop exceeded max_tool_roundtrips={config.max_tool_roundtrips}"
            )

        return current_result

    def _build_chat_request_payload_from_messages(
        self,
        messages: List[Dict[str, Any]],
        config: GenerationConfig,
        stream: bool = False,
    ) -> Dict[str, Any]:
        payload = self._build_chat_request_payload(Prompt.from_messages(messages), config, stream=stream)
        payload["messages"] = messages
        return payload

    def _build_responses_followup_payload(
        self,
        config: GenerationConfig,
        previous_response_id: str,
        tool_outputs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": config.model or self.default_model,
            "input": tool_outputs,
            "previous_response_id": previous_response_id,
            "max_output_tokens": config.max_tokens,
        }

        optional_fields = {
            "temperature": config.temperature,
            "top_p": config.top_p,
            "tools": config.tools,
            "tool_choice": config.tool_choice,
            "metadata": config.metadata,
            "include": config.include,
            "store": config.store,
            "service_tier": config.service_tier,
            "parallel_tool_calls": config.parallel_tool_calls,
        }

        for field_name, value in optional_fields.items():
            if value is not None:
                payload[field_name] = value

        if config.reasoning_effort:
            payload["reasoning"] = {"effort": config.reasoning_effort}

        return payload

    async def _build_chat_tool_messages(
        self,
        tool_calls: List[Dict[str, Any]],
        config: GenerationConfig,
    ) -> List[Dict[str, Any]]:
        outputs = await self._execute_tool_calls(tool_calls, config)
        messages: List[Dict[str, Any]] = []
        for output in outputs:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": output["call_id"],
                    "content": output["output"],
                }
            )
        return messages

    async def _execute_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        config: GenerationConfig,
    ) -> List[Dict[str, Any]]:
        if config.tool_executor is None:
            raise RuntimeError("tool_executor is required to execute tool calls")

        outputs: List[Dict[str, Any]] = []
        for tool_call in tool_calls:
            result = config.tool_executor(tool_call)
            if isawaitable(result):
                result = await result

            outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": tool_call.get("call_id") or tool_call.get("id"),
                    "output": self._serialize_tool_output(result),
                }
            )

        return outputs

    @staticmethod
    def _serialize_tool_output(result: Any) -> str:
        if result is None:
            return ""
        if isinstance(result, str):
            return result
        try:
            return json.dumps(result, ensure_ascii=False)
        except TypeError:
            return str(result)

    def _result_from_chat_response(
        self,
        response: Any,
        config: GenerationConfig,
    ) -> GenerationResult:
        if not response.choices:
            raise RuntimeError("API returned empty content")

        choice = response.choices[0]
        content = self._extract_text(getattr(choice.message, "content", None))
        tool_calls = self._extract_tool_calls(getattr(choice, "message", None))
        if not content and not tool_calls:
            raise RuntimeError("API returned empty content")

        usage = getattr(response, "usage", None)
        return GenerationResult(
            content=content or "",
            token_usage=TokenUsage(
                input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            ),
            finish_reason=getattr(choice, "finish_reason", None),
            model=getattr(response, "model", None) or config.model or self.default_model,
            provider="openai-chat-completions",
            raw_response=response,
            tool_calls=tool_calls,
            response_id=getattr(response, "id", None),
        )

    def _result_from_responses_response(
        self,
        response: Any,
        config: GenerationConfig,
    ) -> GenerationResult:
        content = self._extract_responses_output_text(response)
        tool_calls = self._extract_responses_tool_calls(getattr(response, "output", None))
        if not content and not tool_calls:
            raise RuntimeError("Responses API returned empty content")

        usage = getattr(response, "usage", None)
        return GenerationResult(
            content=content or "",
            token_usage=TokenUsage(
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
            ),
            finish_reason=getattr(response, "status", None),
            model=getattr(response, "model", None) or config.model or self.default_model,
            provider="openai-responses",
            raw_response=response,
            tool_calls=tool_calls,
            response_id=getattr(response, "id", None),
        )

    def _chat_assistant_message_from_result(
        self,
        response: Any,
        result: GenerationResult,
    ) -> Optional[Dict[str, Any]]:
        if response is None or not getattr(response, "choices", None):
            return None

        message = response.choices[0].message
        tool_calls = self._extract_tool_calls(message)
        return {
            "role": "assistant",
            "content": self._extract_text(getattr(message, "content", None)) or "",
            "tool_calls": [
                {
                    "id": tool_call["id"],
                    "type": tool_call["type"],
                    "function": {
                        "name": tool_call["name"],
                        "arguments": tool_call["arguments"],
                    },
                }
                for tool_call in (tool_calls or [])
            ],
        }

    @staticmethod
    def _coerce_content_to_text(content: Any) -> str:
        text = OpenAIProvider._extract_text(content)
        if text:
            return text
        if isinstance(content, str):
            return content
        raise ValueError("Message content could not be converted to text")

    @staticmethod
    def _extract_text(content: Any) -> str:
        if content is None:
            return ""

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                text = OpenAIProvider._extract_text_from_part(item)
                if text:
                    parts.append(text)
            return "".join(parts)

        return ""

    @staticmethod
    def _extract_text_from_part(item: Any) -> str:
        if isinstance(item, str):
            return item

        if isinstance(item, dict):
            if isinstance(item.get("text"), str):
                return item["text"]

            nested_text = item.get("text", {})
            if isinstance(nested_text, dict) and isinstance(nested_text.get("value"), str):
                return nested_text["value"]

        text = getattr(item, "text", None)
        if isinstance(text, str):
            return text

        return ""

    @staticmethod
    def _extract_tool_calls(message: Optional[Any]) -> Optional[List[Dict[str, Any]]]:
        tool_calls = getattr(message, "tool_calls", None)
        if not tool_calls:
            return None

        normalized: List[Dict[str, Any]] = []
        for tool_call in tool_calls:
            function = getattr(tool_call, "function", None)
            normalized.append(
                {
                    "id": getattr(tool_call, "id", None),
                    "type": getattr(tool_call, "type", None),
                    "name": getattr(function, "name", None) if function else None,
                    "arguments": getattr(function, "arguments", None) if function else None,
                }
            )

        return normalized

    @staticmethod
    def _extract_responses_output_text(response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        output_items = getattr(response, "output", None) or []
        parts: List[str] = []
        for item in output_items:
            item_type = getattr(item, "type", None) or (
                item.get("type") if isinstance(item, dict) else None
            )
            if item_type != "message":
                continue

            content = getattr(item, "content", None)
            if content is None and isinstance(item, dict):
                content = item.get("content")

            parts.append(OpenAIProvider._extract_text(content))

        return "".join(part for part in parts if part)

    @staticmethod
    def _extract_responses_tool_calls(output_items: Optional[Iterable[Any]]) -> Optional[List[Dict[str, Any]]]:
        if not output_items:
            return None

        normalized: List[Dict[str, Any]] = []
        for item in output_items:
            item_type = getattr(item, "type", None) or (
                item.get("type") if isinstance(item, dict) else None
            )
            if item_type != "function_call":
                continue

            normalized.append(
                {
                    "id": getattr(item, "id", None) or (item.get("id") if isinstance(item, dict) else None),
                    "type": item_type,
                    "call_id": getattr(item, "call_id", None) or (
                        item.get("call_id") if isinstance(item, dict) else None
                    ),
                    "name": getattr(item, "name", None) or (
                        item.get("name") if isinstance(item, dict) else None
                    ),
                    "arguments": getattr(item, "arguments", None) or (
                        item.get("arguments") if isinstance(item, dict) else None
                    ),
                }
            )

        return normalized or None

    @staticmethod
    def _extract_responses_stream_text(event: Any) -> str:
        event_type = getattr(event, "type", None) or (
            event.get("type") if isinstance(event, dict) else None
        )
        if event_type == "response.output_text.delta":
            delta = getattr(event, "delta", None)
            if delta is None and isinstance(event, dict):
                delta = event.get("delta")
            if isinstance(delta, str):
                return delta
        if event_type == "response.output_text.done":
            text = getattr(event, "text", None)
            if text is None and isinstance(event, dict):
                text = event.get("text")
            if isinstance(text, str):
                return text
        return ""
