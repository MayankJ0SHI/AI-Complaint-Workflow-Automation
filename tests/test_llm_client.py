import os
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from src.llm.llm_client import LLMClient
from src.models.model_schema import ModelTier


class TestResponse(BaseModel):
    """Test schema for structured LLM responses."""

    answer: str
    confidence: float


def create_mock_response(
    content: str,
    total_tokens: int = 25,
) -> MagicMock:
    """Create a mock LiteLLM response."""

    response = MagicMock()

    response.choices[0].message.content = content
    response.usage.total_tokens = total_tokens

    return response


@pytest.fixture
def llm_client():
    """Create an LLMClient with deterministic test configuration."""

    with patch.dict(
        os.environ,
        {"OPENAI_API_KEY": "test-api-key"},
    ):
        return LLMClient(
            max_retries=0,
            timeout=10,
        )


def test_llm_client_requires_api_key():
    """LLMClient should fail when the API key is missing."""

    with patch.dict(
        os.environ,
        {},
        clear=True,
    ):
        with pytest.raises(
            ValueError,
            match="OPENAI_API_KEY is not configured",
        ):
            LLMClient()


def test_llm_client_uses_configured_values():
    """Explicit retry and timeout values should be applied."""

    with patch.dict(
        os.environ,
        {"OPENAI_API_KEY": "test-api-key"},
    ):
        client = LLMClient(
            max_retries=5,
            timeout=30,
        )

    assert client.max_retries == 5
    assert client.timeout == 30


def test_normalize_role():
    """LangChain roles should be converted to OpenAI-compatible roles."""

    assert LLMClient._normalize_role("human") == "user"
    assert LLMClient._normalize_role("ai") == "assistant"
    assert LLMClient._normalize_role("system") == "system"


def test_normalize_role_preserves_unknown_roles():
    """Unknown roles should be returned unchanged."""

    assert LLMClient._normalize_role("tool") == "tool"
    assert LLMClient._normalize_role("custom") == "custom"


def test_format_messages():
    """LangChain messages should be converted to dictionaries."""

    messages = [
        SystemMessage(content="You are a helpful assistant."),
        HumanMessage(content="What is Python?"),
        AIMessage(content="Python is a programming language."),
    ]

    formatted = LLMClient._format_messages(messages)

    assert formatted == [
        {
            "role": "system",
            "content": "You are a helpful assistant.",
        },
        {
            "role": "user",
            "content": "What is Python?",
        },
        {
            "role": "assistant",
            "content": "Python is a programming language.",
        },
    ]


def test_get_total_tokens_returns_token_count():
    """Token usage should be extracted from the LiteLLM response."""

    response = create_mock_response(
        content="Hello",
        total_tokens=42,
    )

    assert LLMClient._get_total_tokens(response) == 42


def test_get_total_tokens_returns_none_when_usage_missing():
    """Missing usage information should return None."""

    response = MagicMock()
    response.usage = None

    assert LLMClient._get_total_tokens(response) is None


def test_parse_structured_response():
    """Valid JSON should be converted into the requested Pydantic model."""

    result = LLMClient._parse_structured_response(
        content='{"answer": "Python", "confidence": 0.95}',
        response_model=TestResponse,
        model="test-model",
    )

    assert isinstance(result, TestResponse)
    assert result.answer == "Python"
    assert result.confidence == 0.95


def test_parse_structured_response_rejects_empty_content():
    """Empty structured output should raise ValueError."""

    with pytest.raises(
        ValueError,
        match="LLM returned empty structured response",
    ):
        LLMClient._parse_structured_response(
            content=None,
            response_model=TestResponse,
            model="test-model",
        )


def test_parse_structured_response_rejects_invalid_json():
    """Invalid JSON should fail structured response validation."""

    with pytest.raises(Exception):
        LLMClient._parse_structured_response(
            content="not-valid-json",
            response_model=TestResponse,
            model="test-model",
        )


def test_parse_structured_response_rejects_invalid_schema():
    """Valid JSON with an invalid schema should fail validation."""

    with pytest.raises(Exception):
        LLMClient._parse_structured_response(
            content='{"answer": "Python"}',
            response_model=TestResponse,
            model="test-model",
        )


def test_call_model_returns_text_response(llm_client):
    """Normal LLM calls should return plain text."""

    mock_response = create_mock_response(
        content="Python is a programming language.",
        total_tokens=20,
    )

    with patch(
        "src.llm.llm_client.completion",
        return_value=mock_response,
    ) as mock_completion:

        result = llm_client._call_model(
            model="test-model",
            messages=[
                {
                    "role": "user",
                    "content": "What is Python?",
                }
            ],
            tier=ModelTier.GENERIC,
            is_fallback=False,
        )

    assert result == "Python is a programming language."

    mock_completion.assert_called_once_with(
        model="test-model",
        messages=[
            {
                "role": "user",
                "content": "What is Python?",
            }
        ],
        timeout=10,
        num_retries=0,
    )


def test_call_model_passes_response_format_for_structured_output(
    llm_client,
):
    """Structured calls should pass the Pydantic model as response_format."""

    mock_response = create_mock_response(
        content='{"answer": "Python", "confidence": 0.95}',
    )

    with patch(
        "src.llm.llm_client.completion",
        return_value=mock_response,
    ) as mock_completion:

        result = llm_client._call_model(
            model="test-model",
            messages=[
                {
                    "role": "user",
                    "content": "What is Python?",
                }
            ],
            tier=ModelTier.BASIC,
            is_fallback=False,
            response_model=TestResponse,
        )

    assert isinstance(result, TestResponse)
    assert result.answer == "Python"
    assert result.confidence == 0.95

    mock_completion.assert_called_once_with(
        model="test-model",
        messages=[
            {
                "role": "user",
                "content": "What is Python?",
            }
        ],
        timeout=10,
        num_retries=0,
        response_format=TestResponse,
    )


def test_invoke_formats_messages_and_calls_workflow(llm_client):
    """invoke() should format LangChain messages before routing."""

    expected_result = "Generated answer"

    with patch.object(
        llm_client,
        "_invoke_with_fallback",
        return_value=expected_result,
    ) as mock_router:

        messages = [
            SystemMessage(content="You are helpful."),
            HumanMessage(content="Hello"),
        ]

        result = llm_client.invoke(
            messages=messages,
            tier=ModelTier.BASIC,
        )

    assert result == expected_result

    mock_router.assert_called_once_with(
        messages=[
            {
                "role": "system",
                "content": "You are helpful.",
            },
            {
                "role": "user",
                "content": "Hello",
            },
        ],
        tier=ModelTier.BASIC,
        response_model=None,
    )


def test_invoke_with_fallback_uses_primary_model(llm_client):
    """A successful primary model call should not invoke fallback."""

    primary_result = "Primary response"

    with patch.object(
        llm_client,
        "_call_model",
        return_value=primary_result,
    ) as mock_call:

        result = llm_client._invoke_with_fallback(
            messages=[
                {
                    "role": "user",
                    "content": "Hello",
                }
            ],
            tier=ModelTier.BASIC,
            response_model=None,
        )

    assert result == primary_result

    assert mock_call.call_count == 1

    assert mock_call.call_args.kwargs["is_fallback"] is False


def test_invoke_with_fallback_uses_fallback_after_primary_failure(
    llm_client,
):
    """Fallback model should be called when the primary model fails."""

    fallback_result = "Fallback response"

    with patch.object(
        llm_client,
        "_call_model",
        side_effect=[
            RuntimeError("Primary model unavailable"),
            fallback_result,
        ],
    ) as mock_call:

        result = llm_client._invoke_with_fallback(
            messages=[
                {
                    "role": "user",
                    "content": "Hello",
                }
            ],
            tier=ModelTier.BASIC,
            response_model=None,
        )

    assert result == fallback_result

    assert mock_call.call_count == 2

    first_call = mock_call.call_args_list[0]
    second_call = mock_call.call_args_list[1]

    assert first_call.kwargs["is_fallback"] is False
    assert second_call.kwargs["is_fallback"] is True


def test_invoke_with_fallback_raises_when_both_models_fail(
    llm_client,
):
    """RuntimeError should be raised when both models fail."""

    with patch.object(
        llm_client,
        "_call_model",
        side_effect=[
            RuntimeError("Primary failure"),
            RuntimeError("Fallback failure"),
        ],
    ):

        with pytest.raises(
            RuntimeError,
            match="Both primary and fallback models failed",
        ):
            llm_client._invoke_with_fallback(
                messages=[
                    {
                        "role": "user",
                        "content": "Hello",
                    }
                ],
                tier=ModelTier.GENERIC,
                response_model=None,
            )