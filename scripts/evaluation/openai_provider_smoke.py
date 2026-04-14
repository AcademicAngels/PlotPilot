"""OpenAI/OpenAI-compatible provider smoke test.

Usage:
  python3 scripts/evaluation/openai_provider_smoke.py --mode chat
  python3 scripts/evaluation/openai_provider_smoke.py --mode responses --tool-loop
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from domain.ai.services.llm_service import GenerationConfig
from domain.ai.value_objects.prompt import Prompt
from infrastructure.ai.config.settings import Settings
from infrastructure.ai.providers.openai_provider import OpenAIProvider


def _build_provider(api_mode: str) -> OpenAIProvider:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required")

    return OpenAIProvider(
        Settings(
            api_key=api_key,
            base_url=os.getenv("OPENAI_BASE_URL"),
            default_model=os.getenv("OPENAI_MODEL", "gpt-5.4"),
            timeout=float(os.getenv("OPENAI_TIMEOUT", "120")),
            max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "2")),
            api_mode=api_mode,
        )
    )


async def _tool_executor(tool_call):
    arguments = tool_call.get("arguments") or "{}"
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        parsed = {"raw": arguments}

    return {
        "echo_name": tool_call.get("name"),
        "echo_arguments": parsed,
        "status": "ok",
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["chat", "responses"], default="chat")
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--tool-loop", action="store_true")
    args = parser.parse_args()

    provider = _build_provider(args.mode)
    tools = None
    tool_executor = None
    user_prompt = "Return a short sentence proving the provider works."

    if args.tool_loop:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "echo_lookup",
                    "description": "Echoes the received query for smoke testing.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        },
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                },
            }
        ]
        tool_executor = _tool_executor
        user_prompt = "Call echo_lookup with query='provider smoke test' and summarize the result."

    prompt = Prompt(
        system="You are a concise API smoke test assistant.",
        user=user_prompt,
    )
    config = GenerationConfig(
        model=os.getenv("OPENAI_MODEL", "gpt-5.4"),
        api_mode=args.mode,
        reasoning_effort="medium" if args.mode == "responses" else None,
        tools=tools,
        tool_choice="auto" if tools else None,
        tool_executor=tool_executor,
        max_tokens=512,
        temperature=0.1,
        max_tool_roundtrips=2,
    )

    if args.stream:
        parts = []
        async for chunk in provider.stream_generate(prompt, config):
            print(chunk, end="", flush=True)
            parts.append(chunk)
        print()
        print(f"\n[stream_complete] chars={sum(len(part) for part in parts)}")
        return

    result = await provider.generate(prompt, config)
    print("provider:", result.provider)
    print("model:", result.model)
    print("finish_reason:", result.finish_reason)
    print("response_id:", result.response_id)
    print("token_usage:", result.token_usage.total_tokens)
    print("content:")
    print(result.content)
    if result.tool_calls:
        print("tool_calls:")
        print(json.dumps(result.tool_calls, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
