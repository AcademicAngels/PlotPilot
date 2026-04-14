"""测试依赖注入配置"""
import os
import pytest
from unittest.mock import patch, MagicMock
from interfaces.api.dependencies import get_vector_store, get_llm_service


class TestGetVectorStore:
    """测试 get_vector_store 依赖注入函数"""

    def test_get_vector_store_returns_none_when_no_env(self):
        """未设置环境变量时返回 None"""
        with patch.dict(os.environ, {}, clear=True):
            result = get_vector_store()
            assert result is not None
            assert result.__class__.__name__ == "ChromaDBVectorStore"

    def test_get_vector_store_returns_none_when_disabled(self):
        """VECTOR_STORE_ENABLED 为 false 时返回 None"""
        with patch.dict(os.environ, {"VECTOR_STORE_ENABLED": "false"}, clear=True):
            result = get_vector_store()
            assert result is None

    def test_get_vector_store_returns_qdrant_when_env_set(self):
        """设置 qdrant 类型时返回 QdrantVectorStore 实例"""
        with patch.dict(os.environ, {
            "VECTOR_STORE_ENABLED": "true",
            "VECTOR_STORE_TYPE": "qdrant",
            "QDRANT_HOST": "localhost",
            "QDRANT_PORT": "6333"
        }, clear=True):
            # Mock QdrantVectorStore to avoid actual connection
            with patch("infrastructure.ai.qdrant_vector_store.QdrantVectorStore") as mock_qdrant:
                mock_instance = MagicMock()
                mock_qdrant.return_value = mock_instance

                result = get_vector_store()

                # 验证返回了实例
                assert result is mock_instance
                # 验证使用正确的参数初始化
                mock_qdrant.assert_called_once_with(
                    host="localhost",
                    port=6333,
                    api_key=None
                )


class TestGetLLMService:
    """测试 LLM provider 选择"""

    def test_get_llm_service_returns_openai_provider_when_configured(self):
        """配置 OPENAI 路径时返回 OpenAIProvider"""
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "openai",
                "OPENAI_API_KEY": "test-api-key",
                "OPENAI_MODEL": "gpt-5.4",
                "OPENAI_TIMEOUT": "45",
                "OPENAI_MAX_RETRIES": "3",
            },
            clear=True,
        ):
            with patch("infrastructure.ai.providers.openai_provider.OpenAIProvider") as mock_provider:
                instance = MagicMock()
                mock_provider.return_value = instance

                result = get_llm_service()

                assert result is instance
                settings = mock_provider.call_args.args[0]
                assert settings.api_key == "test-api-key"
                assert settings.default_model == "gpt-5.4"
                assert settings.timeout == 45.0
                assert settings.max_retries == 3
                assert settings.api_mode == "auto"

    def test_get_llm_service_falls_back_to_mock_when_openai_key_missing(self):
        """未配置 OPENAI key 时降级 MockProvider"""
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}, clear=True):
            result = get_llm_service()
            assert result.__class__.__name__ == "MockProvider"

    def test_get_llm_service_reads_openai_api_mode(self):
        """读取 OPENAI_API_MODE 配置"""
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "openai",
                "OPENAI_API_KEY": "test-api-key",
                "OPENAI_API_MODE": "responses",
            },
            clear=True,
        ):
            with patch("infrastructure.ai.providers.openai_provider.OpenAIProvider") as mock_provider:
                mock_provider.return_value = MagicMock()
                get_llm_service()

                settings = mock_provider.call_args.args[0]
                assert settings.api_mode == "responses"

    def test_get_vector_store_with_custom_host_port(self):
        """使用自定义 host 和 port"""
        with patch.dict(os.environ, {
            "VECTOR_STORE_ENABLED": "true",
            "VECTOR_STORE_TYPE": "qdrant",
            "QDRANT_HOST": "qdrant.example.com",
            "QDRANT_PORT": "6334"
        }, clear=True):
            with patch("infrastructure.ai.qdrant_vector_store.QdrantVectorStore") as mock_qdrant:
                mock_instance = MagicMock()
                mock_qdrant.return_value = mock_instance

                result = get_vector_store()

                mock_qdrant.assert_called_once_with(
                    host="qdrant.example.com",
                    port=6334,
                    api_key=None
                )

    def test_get_vector_store_with_api_key(self):
        """使用 API key"""
        with patch.dict(os.environ, {
            "VECTOR_STORE_ENABLED": "true",
            "VECTOR_STORE_TYPE": "qdrant",
            "QDRANT_HOST": "localhost",
            "QDRANT_PORT": "6333",
            "QDRANT_API_KEY": "test-api-key"
        }, clear=True):
            with patch("infrastructure.ai.qdrant_vector_store.QdrantVectorStore") as mock_qdrant:
                mock_instance = MagicMock()
                mock_qdrant.return_value = mock_instance

                result = get_vector_store()

                mock_qdrant.assert_called_once_with(
                    host="localhost",
                    port=6333,
                    api_key="test-api-key"
                )

    def test_get_vector_store_uses_default_values(self):
        """只设置 qdrant 类型，使用默认 host/port"""
        with patch.dict(os.environ, {
            "VECTOR_STORE_ENABLED": "true",
            "VECTOR_STORE_TYPE": "qdrant",
        }, clear=True):
            with patch("infrastructure.ai.qdrant_vector_store.QdrantVectorStore") as mock_qdrant:
                mock_instance = MagicMock()
                mock_qdrant.return_value = mock_instance

                result = get_vector_store()

                # 验证使用默认值
                mock_qdrant.assert_called_once_with(
                    host="localhost",
                    port=6333,
                    api_key=None
                )
