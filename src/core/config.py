"""
core/config.py
==============
Application settings using **Pydantic BaseSettings**.

All values are read from environment variables or a ``.env`` file at import
time.

Usage::

    from src.core.config import settings

    print(settings.LLM_MODEL)
"""

from __future__ import annotations

import glob
from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    CortexRE runtime configuration.

    All fields map 1-to-1 to environment variables (or .env entries).
    Field names are upper-cased by convention; Pydantic Settings resolves
    them case-insensitively.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",          # silently ignore unknown env vars
    )

    # ------------------------------------------------------------------
    # LLM settings
    # ------------------------------------------------------------------
    LLM_MODEL: str = Field(
        default="openai/gpt-4o-mini",
        description=(
            "LiteLLM model string that selects both the provider and the model. "
            "Examples: 'openai/gpt-4o-mini', 'anthropic/claude-3-5-haiku-20241022', "
            "'ollama/llama3.2', 'gemini/gemini-1.5-flash'. "
            "See https://docs.litellm.ai/docs/providers for the full list."
        ),
    )

    LLM_TEMPERATURE: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description=(
            "Sampling temperature. 0 = deterministic (recommended for "
            "structured extraction); higher values increase creativity."
        ),
    )

    # ------------------------------------------------------------------
    # API keys (LiteLLM reads these automatically from the environment)
    # ------------------------------------------------------------------
    OPENAI_API_KEY: str = Field(
        default="",
        description="OpenAI API key. Required when LLM_MODEL starts with 'openai/'.",
    )

    ANTHROPIC_API_KEY: str = Field(
        default="",
        description="Anthropic API key. Required when LLM_MODEL starts with 'anthropic/'.",
    )

    # ------------------------------------------------------------------
    # Agent behaviour
    # ------------------------------------------------------------------
    MAX_RETRIES: int = Field(
        default=3,
        ge=1,
        description="Maximum retrieval re-tries before the agent gives up.",
    )

    MAX_REVISIONS: int = Field(
        default=3,
        ge=1,
        description="Maximum number of research→critique revision cycles.",
    )

    CRITIQUE_SCORE_THRESHOLD: int = Field(
        default=80,
        ge=0,
        le=100,
        description="Minimum weighted score (0–100) for the critique agent to approve a draft.",
    )

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    DATA_DIR: Path = Field(
        default=Path("data"),
        description="Directory containing the .parquet dataset file(s).",
    )

    # ------------------------------------------------------------------
    # Validators / derived fields
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def resolve_and_validate(self) -> "Settings":
        """Make DATA_DIR absolute and validate that the required API key is set."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        if not self.DATA_DIR.is_absolute():
            self.DATA_DIR = repo_root / self.DATA_DIR

        provider = self.LLM_MODEL.split("/")[0].lower() if "/" in self.LLM_MODEL else ""
        if provider == "openai" and not self.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY must be set when LLM_MODEL starts with 'openai/'."
            )
        if provider == "anthropic" and not self.ANTHROPIC_API_KEY:
            raise ValueError(
                "ANTHROPIC_API_KEY must be set when LLM_MODEL starts with 'anthropic/'."
            )
        return self

    @computed_field  # type: ignore[misc]
    @property
    def DATA_PATH(self) -> Path:
        """Path to the single .parquet file found inside DATA_DIR."""
        matches = glob.glob(str(self.DATA_DIR / "*.parquet"))
        if not matches:
            raise FileNotFoundError(
                f"No .parquet file found in '{self.DATA_DIR}'. "
                "Please place the dataset there before running."
            )
        return Path(matches[0])


# ---------------------------------------------------------------------------
# Singleton — import this everywhere instead of the class directly
# ---------------------------------------------------------------------------

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
