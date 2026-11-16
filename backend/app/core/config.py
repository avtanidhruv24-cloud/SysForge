"""
SysForge backend configuration.

All settings are loaded from environment variables (or a .env file via
python-dotenv).  Import the singleton ``settings`` wherever configuration
is needed — never read ``os.environ`` directly in application code.

Usage::

    from app.core.config import settings

    print(settings.host, settings.port)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings resolved from environment variables.

    The ``model_config`` below tells pydantic-settings to read a ``.env``
    file in the *backend/* directory when running locally.  In CI or
    production the same variables are supplied via the process environment,
    so no ``.env`` file is required.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Extra keys in .env are silently ignored — forward-compatible
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    app_env: Literal["development", "production", "test"] = Field(
        default="development",
        description="Runtime environment.  Controls logging verbosity and debug features.",
    )

    host: str = Field(
        default="127.0.0.1",
        description="Host address uvicorn binds to.",
    )

    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="TCP port uvicorn listens on.",
    )

    log_level: Literal["debug", "info", "warning", "error", "critical"] = Field(
        default="info",
        description="Minimum log level emitted by uvicorn and the application.",
    )

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------

    # Stored as a plain string internally; split into a list via the
    # property below.  Using ``str`` here prevents pydantic-settings from
    # attempting JSON decoding on a bare URL like ``http://localhost:5173``.
    cors_origins_raw: str = Field(
        default="http://localhost:5173",
        alias="cors_origins",
        description=(
            "Comma-separated list of allowed CORS origins.  "
            "The SysForge Vite frontend runs on 5173 by default."
        ),
    )

    @property
    def cors_origins(self) -> list[str]:
        """Return CORS origins as a list, split on commas."""
        return [
            origin.strip()
            for origin in self.cors_origins_raw.split(",")
            if origin.strip()
        ]

    # ------------------------------------------------------------------
    # API metadata
    # ------------------------------------------------------------------

    api_prefix: str = Field(
        default="/api/v1",
        description="Version prefix applied to all SysForge API routes.",
    )

    app_title: str = "SysForge API"
    app_description: str = (
        "Intelligent Integrated System Programming Toolchain — backend service."
    )
    app_version: str = "1.0.0"

    # ------------------------------------------------------------------
    # VM safety limits  (values read now; enforcement added in VM phase)
    # ------------------------------------------------------------------

    vm_max_instructions: int = Field(
        default=100_000,
        ge=1,
        description="Maximum instruction count per VM execution run.",
    )

    vm_max_memory_words: int = Field(
        default=65_536,
        ge=1,
        description="Maximum addressable words in the educational VM memory.",
    )

    vm_max_output_lines: int = Field(
        default=1_000,
        ge=1,
        description="Maximum lines the PRINT instruction may produce per run.",
    )

    vm_execution_timeout_seconds: int = Field(
        default=10,
        ge=1,
        description="Wall-clock timeout (seconds) for a single VM execution run.",
    )

    # ------------------------------------------------------------------
    # Future — AI service (unused in Phase 2)
    # ------------------------------------------------------------------

    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key.  Not required until the AI phase.",
    )

    ai_model: str = Field(
        default="gpt-4o",
        description="LLM model identifier used by the AI explanation service.",
    )

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached ``Settings`` singleton.

    Using ``@lru_cache`` means the .env file is read exactly once per
    process.  In tests, call ``get_settings.cache_clear()`` after patching
    environment variables to force a fresh read.
    """
    return Settings()


def _get_settings_lazy() -> Settings:
    """Return settings, creating the singleton on first call."""
    return get_settings()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
# NOTE: This is a *lazy* proxy — the real Settings object is not constructed
# until ``settings`` is first *accessed*.  This allows conftest.py to set
# environment variables before the singleton is materialised.
#
# For direct use: ``from app.core.config import settings``
# For testing:    call ``get_settings.cache_clear()`` then re-import or
#                 use ``get_settings()`` directly.

class _SettingsProxy:
    """Thin proxy that forwards attribute access to the cached Settings."""

    __slots__ = ()

    def __getattr__(self, name: str):  # type: ignore[override]
        return getattr(get_settings(), name)

    def __repr__(self) -> str:
        return repr(get_settings())


settings: Settings = _SettingsProxy()  # type: ignore[assignment]
