from pydantic import BaseModel, Field
from enum import Enum


class ModelConfig(BaseModel):
    """Configuration for a primary and fallback LLM."""

    primary: str = Field(min_length=1)
    fallback: str = Field(min_length=1)


class ModelsConfig(BaseModel):
    """LLM configuration grouped by model tier."""

    basic: ModelConfig
    generic: ModelConfig
    complex: ModelConfig


class LLMConfig(BaseModel):
    """Runtime configuration for LLM calls."""

    timeout: int = Field(default=60, gt=0)
    max_retries: int = Field(default=2, ge=0)


class ModelTier(str, Enum):
    """Defines the complexity and cost tier of an LLM request."""

    BASIC = "basic"
    GENERIC = "generic"
    COMPLEX = "complex"


class LLMSettings(BaseModel):
    """Complete LLM configuration."""

    llm: LLMConfig
    models: ModelsConfig

    def get_tier(self, tier: ModelTier) -> ModelConfig:
        """Return the model configuration for the requested tier."""
        return getattr(self.models, tier.value)
