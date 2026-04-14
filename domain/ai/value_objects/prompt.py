# domain/ai/value_objects/prompt.py
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Prompt:
    """提示词值对象"""
    system: str = ""
    user: str = ""
    messages: Optional[List[Dict[str, Any]]] = None

    def __post_init__(self):
        if self.messages is not None:
            normalized_messages = self._normalize_messages(self.messages)
            object.__setattr__(self, "messages", normalized_messages)

            if not self.system:
                derived_system = self._derive_message_text(
                    normalized_messages,
                    roles={"system", "developer"},
                    reverse=False,
                )
                if derived_system:
                    object.__setattr__(self, "system", derived_system)

            if not self.user:
                derived_user = self._derive_message_text(
                    normalized_messages,
                    roles={"user"},
                    reverse=True,
                )
                if derived_user:
                    object.__setattr__(self, "user", derived_user)
            return

        if not self.user or not self.user.strip():
            raise ValueError("User message cannot be empty")
        if not self.system or not self.system.strip():
            raise ValueError("System message cannot be empty")

    @classmethod
    def from_messages(cls, messages: List[Dict[str, Any]]) -> "Prompt":
        """从通用消息列表构建 Prompt。"""
        return cls(messages=messages)

    def to_messages(self) -> List[Dict[str, Any]]:
        """转换为消息列表格式"""
        if self.messages is not None:
            return [dict(message) for message in self.messages]

        messages = []
        if self.system:
            messages.append({"role": "system", "content": self.system})
        messages.append({"role": "user", "content": self.user})
        return messages

    @staticmethod
    def _normalize_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not messages:
            raise ValueError("messages cannot be empty")

        allowed_roles = {"system", "developer", "user", "assistant", "tool", "function"}
        normalized: List[Dict[str, Any]] = []

        for message in messages:
            if not isinstance(message, dict):
                raise ValueError("Each message must be a dictionary")

            role = message.get("role")
            if role not in allowed_roles:
                raise ValueError(f"Unsupported message role: {role}")

            if "content" not in message:
                raise ValueError("Each message must include content")

            normalized.append(dict(message))

        return normalized

    @staticmethod
    def _derive_message_text(
        messages: List[Dict[str, Any]],
        roles: set[str],
        reverse: bool,
    ) -> str:
        items = reversed(messages) if reverse else messages
        for message in items:
            if message.get("role") not in roles:
                continue

            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content

        return ""
