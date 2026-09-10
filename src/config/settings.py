from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApplicationSettings(BaseSettings):
    """
    Application-level configuration loaded from environment variables.
    """

    api_base_url: str = Field(
        default="http://127.0.0.1:8000",
        description="Base URL of the FastAPI service.",
    )

    input_dir: str = Field(
        default="data/input/complaints",
        description="Default input directory for CLI processing.",
    )

    output_dir: str = Field(
        default="output",
        description="Default output directory.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> ApplicationSettings:
    """
    Return a cached application settings instance.
    """

    return ApplicationSettings()


settings = get_settings()
