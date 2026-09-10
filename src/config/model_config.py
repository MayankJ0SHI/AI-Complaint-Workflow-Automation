from pathlib import Path

import yaml

from src.models.model_schema import LLMSettings

CONFIG_PATH = Path(__file__).parent / "models.yaml"


def load_model_config() -> LLMSettings:
    """Load and validate LLM configuration."""

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Model configuration file not found: {CONFIG_PATH}")

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config_data = yaml.safe_load(file)

    return LLMSettings.model_validate(config_data)


MODEL_SETTINGS = load_model_config()