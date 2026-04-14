"""Runtime-persisted LLM provider configuration helpers.

The application boots from the repository root `.env`, so the safest way to
support a UI-managed provider configuration is:
1. Persist managed keys into `.env`
2. Mirror the values into `os.environ` for the current process
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Dict, Iterable, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = PROJECT_ROOT / ".env"

MANAGED_KEYS = [
    "LLM_PROVIDER",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL",
    "OPENAI_API_MODE",
    "OPENAI_TIMEOUT",
    "OPENAI_MAX_RETRIES",
    "OPENAI_EMBEDDING_MODEL",
    "OPENAI_EMBEDDING_DIMENSION",
]


def _read_env_lines(path: Path = ENV_PATH) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def _parse_env(lines: Iterable[str]) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        parsed[key.strip()] = value.strip().split("#")[0].strip()
    return parsed


def _mask_secret(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}***{value[-4:]}"


@dataclass
class OpenAICompatibleConfigSnapshot:
    llm_provider: str
    has_api_key: bool
    api_key_masked: Optional[str]
    base_url: str
    model: str
    api_mode: str
    timeout: int
    max_retries: int
    embedding_model: str
    embedding_dimension: Optional[int]


def read_openai_compatible_config() -> OpenAICompatibleConfigSnapshot:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    dimension_raw = os.getenv("OPENAI_EMBEDDING_DIMENSION", "").strip()
    embedding_dimension = int(dimension_raw) if dimension_raw.isdigit() else None
    return OpenAICompatibleConfigSnapshot(
        llm_provider=os.getenv("LLM_PROVIDER", "anthropic").strip() or "anthropic",
        has_api_key=bool(api_key),
        api_key_masked=_mask_secret(api_key),
        base_url=os.getenv("OPENAI_BASE_URL", "").strip(),
        model=os.getenv("OPENAI_MODEL", "gpt-5.4").strip() or "gpt-5.4",
        api_mode=os.getenv("OPENAI_API_MODE", "auto").strip() or "auto",
        timeout=int(float(os.getenv("OPENAI_TIMEOUT", "120").strip() or "120")),
        max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "2").strip() or "2"),
        embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip()
        or "text-embedding-3-small",
        embedding_dimension=embedding_dimension,
    )


def persist_openai_compatible_config(values: Dict[str, Optional[str]], path: Path = ENV_PATH) -> None:
    lines = _read_env_lines(path)
    existing = _parse_env(lines)

    for key in MANAGED_KEYS:
        if key in values:
            value = values[key]
            if value is None or value == "":
                existing.pop(key, None)
            else:
                existing[key] = str(value)

    updated_lines: list[str] = []
    remaining_keys = set(existing.keys())

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            updated_lines.append(line)
            continue

        key, _, _ = stripped.partition("=")
        key = key.strip()
        if key in MANAGED_KEYS:
            if key in existing:
                updated_lines.append(f"{key}={existing[key]}")
                remaining_keys.discard(key)
            continue

        updated_lines.append(line)

    managed_to_append = [key for key in MANAGED_KEYS if key in remaining_keys]
    if managed_to_append:
        if updated_lines and updated_lines[-1].strip():
            updated_lines.append("")
        updated_lines.append("# Managed by PlotPilot UI: OpenAI-compatible configuration")
        for key in managed_to_append:
            updated_lines.append(f"{key}={existing[key]}")

    if not updated_lines:
        updated_lines = ["# Managed by PlotPilot UI: OpenAI-compatible configuration"]
        for key in MANAGED_KEYS:
            if key in existing:
                updated_lines.append(f"{key}={existing[key]}")

    path.write_text("\n".join(updated_lines).rstrip() + "\n", encoding="utf-8")


def apply_openai_compatible_env(values: Dict[str, Optional[str]]) -> None:
    for key, value in values.items():
        if key not in MANAGED_KEYS:
            continue
        if value is None or value == "":
            os.environ.pop(key, None)
        else:
            os.environ[key] = str(value)
