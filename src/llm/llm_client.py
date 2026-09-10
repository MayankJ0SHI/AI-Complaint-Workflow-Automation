import os
import time
from typing import Any, TypeVar

from dotenv import load_dotenv
from litellm import completion
from pydantic import BaseModel

from src.config.model_config import MODEL_SETTINGS
from src.models.model_schema import ModelTier
from src.logger.logger import get_logger

load_dotenv()

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """
    Centralized LiteLLM client.

    Responsibilities:
        - Model tier selection
        - Primary/fallback model handling
        - Retry configuration
        - Timeout handling
        - LangChain message conversion
        - Normal text generation
        - Structured Pydantic output
        - Latency logging
        - Token usage logging
    """

    def __init__(
        self,
        max_retries: int | None = None,
        timeout: int | None = None,
    ) -> None:
        """
        Initialize the LLM client.

        Args:
            max_retries:
                Number of retries performed by LiteLLM.
                If None, the configured value is used.

            timeout:
                Maximum time allowed for an individual LLM request.
                If None, the configured value is used.
        """

        if not os.getenv("OPENAI_API_KEY"):
            logger.critical("OPENAI_API_KEY is not configured")
            raise ValueError("OPENAI_API_KEY is not configured")

        self.max_retries = (
            MODEL_SETTINGS.llm.max_retries if max_retries is None else max_retries
        )

        self.timeout = MODEL_SETTINGS.llm.timeout if timeout is None else timeout

        logger.info(
            "LLM client initialized | max_retries=%s | timeout=%ss",
            self.max_retries,
            self.timeout,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def invoke(
        self,
        messages: list[Any],
        tier: ModelTier = ModelTier.GENERIC,
        response_model: type[T] | None = None,
    ) -> str | T:
        """
        Invoke the LLM.

        Args:
            messages:
                LangChain messages such as SystemMessage,
                HumanMessage, and AIMessage.

            tier:
                Complexity/cost tier used to select the model.

            response_model:
                Optional Pydantic model for structured output.

        Returns:
            str:
                Normal text response.

            T:
                Validated Pydantic model when response_model is provided.
        """

        formatted_messages = self._format_messages(messages)

        logger.info(
            "LLM invocation started | tier=%s | structured=%s | schema=%s",
            tier.value,
            response_model is not None,
            response_model.__name__ if response_model else None,
        )

        return self._invoke_with_fallback(
            messages=formatted_messages,
            tier=tier,
            response_model=response_model,
        )

    # ------------------------------------------------------------------
    # Primary / Fallback
    # ------------------------------------------------------------------

    def _invoke_with_fallback(
        self,
        messages: list[dict[str, Any]],
        tier: ModelTier,
        response_model: type[T] | None,
    ) -> str | T:
        """
        Execute the primary model and use the fallback model
        if the primary model fails.
        """

        config = MODEL_SETTINGS.get_tier(tier)

        primary_model = config.primary
        fallback_model = config.fallback

        logger.info(
            "Model routing | tier=%s | primary=%s | fallback=%s",
            tier.value,
            primary_model,
            fallback_model,
        )

        # --------------------------------------------------------------
        # Primary model
        # --------------------------------------------------------------

        try:
            return self._call_model(
                model=primary_model,
                messages=messages,
                tier=tier,
                is_fallback=False,
                response_model=response_model,
            )

        except Exception as primary_error:
            logger.warning(
                "Primary model failed | tier=%s | model=%s | error=%s",
                tier.value,
                primary_model,
                primary_error,
            )

        # --------------------------------------------------------------
        # Fallback model
        # --------------------------------------------------------------

        logger.info(
            "Attempting fallback model | tier=%s | model=%s",
            tier.value,
            fallback_model,
        )

        try:
            return self._call_model(
                model=fallback_model,
                messages=messages,
                tier=tier,
                is_fallback=True,
                response_model=response_model,
            )

        except Exception as fallback_error:
            logger.exception(
                "Fallback model failed | tier=%s | model=%s",
                tier.value,
                fallback_model,
            )

            raise RuntimeError(
                f"Both primary and fallback models failed " f"for tier '{tier.value}'"
            ) from fallback_error

    # ------------------------------------------------------------------
    # LiteLLM Call
    # ------------------------------------------------------------------

    def _call_model(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tier: ModelTier,
        is_fallback: bool,
        response_model: type[T] | None = None,
    ) -> str | T:
        """
        Execute a single LiteLLM request.

        When response_model is provided, LiteLLM is instructed to
        return a structured response matching the Pydantic schema.
        """

        start_time = time.perf_counter()

        logger.info(
            "Calling LLM | model=%s | tier=%s | fallback=%s | structured=%s",
            model,
            tier.value,
            is_fallback,
            response_model is not None,
        )

        try:
            request_kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "timeout": self.timeout,
                "num_retries": self.max_retries,
            }

            if response_model is not None:
                request_kwargs["response_format"] = response_model

            response = completion(**request_kwargs)

            content = response.choices[0].message.content

            latency = time.perf_counter() - start_time

            total_tokens = self._get_total_tokens(response)

            logger.info(
                "LLM request completed | "
                "model=%s | tier=%s | fallback=%s | "
                "latency=%.2fs | tokens=%s",
                model,
                tier.value,
                is_fallback,
                latency,
                total_tokens,
            )

            # ----------------------------------------------------------
            # Structured response
            # ----------------------------------------------------------

            if response_model is not None:
                return self._parse_structured_response(
                    content=content,
                    response_model=response_model,
                    model=model,
                )

            # ----------------------------------------------------------
            # Normal response
            # ----------------------------------------------------------

            return content

        except Exception:
            latency = time.perf_counter() - start_time

            logger.exception(
                "LLM request failed | "
                "model=%s | tier=%s | fallback=%s | "
                "latency=%.2fs",
                model,
                tier.value,
                is_fallback,
                latency,
            )

            raise

    # ------------------------------------------------------------------
    # Structured Response
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_structured_response(
        content: str | None,
        response_model: type[T],
        model: str,
    ) -> T:
        """
        Validate an LLM response against a Pydantic model.
        """

        if not content:
            raise ValueError(
                f"LLM returned empty structured response " f"for model '{model}'"
            )

        logger.info(
            "Validating structured response | schema=%s",
            response_model.__name__,
        )

        try:
            result = response_model.model_validate_json(content)

        except Exception:
            logger.exception(
                "Structured response validation failed | " "schema=%s | model=%s",
                response_model.__name__,
                model,
            )
            raise

        logger.info(
            "Structured response validation successful | schema=%s",
            response_model.__name__,
        )

        return result

    # ------------------------------------------------------------------
    # Token Usage
    # ------------------------------------------------------------------

    @staticmethod
    def _get_total_tokens(response: Any) -> int | None:
        """
        Extract total token usage from a LiteLLM response.
        """

        usage = getattr(response, "usage", None)

        if usage is None:
            return None

        return getattr(usage, "total_tokens", None)

    # ------------------------------------------------------------------
    # Message Formatting
    # ------------------------------------------------------------------

    @classmethod
    def _format_messages(
        cls,
        messages: list[Any],
    ) -> list[dict[str, Any]]:
        """
        Convert LangChain messages into LiteLLM/OpenAI-compatible
        message dictionaries.
        """

        return [
            {
                "role": cls._normalize_role(message.type),
                "content": message.content,
            }
            for message in messages
        ]

    # ------------------------------------------------------------------
    # Role Normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_role(role: str) -> str:
        """
        Convert LangChain message roles into OpenAI-compatible roles.
        """

        role_mapping = {
            "human": "user",
            "ai": "assistant",
            "system": "system",
        }

        return role_mapping.get(role, role)
